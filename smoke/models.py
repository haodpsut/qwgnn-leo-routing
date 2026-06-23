"""
Three param-matched GNNs that differ ONLY in their propagation operator.

  GCN      : local 1-hop averaging  A_hat @ H        (receptive field = depth)
  HeatGNN  : global classical diffusion  exp(-t L) @ H        (real, diffusive)
  QWGNN    : global quantum walk  | exp(-i t L) @ H |          (complex, ballistic)

Everything outside the operator is identical: each layer is
    H <- ReLU( Linear_{d->d}( Op(H) ) )
followed by a shared Linear_{d->1} readout. The only parameter difference is a
single learnable scalar t per global layer (negligible), so any performance gap
is attributable to the operator, not to capacity. The decisive comparison is
QWGNN vs HeatGNN: same global reach, the sole difference being the imaginary
(ballistic, interfering) vs real (diffusive, decaying) exponent.

The global operators are realized exactly through the eigendecomposition of the
symmetric normalized Laplacian, computed once per graph:
    L = I - D^{-1/2} A D^{-1/2} = V diag(lambda) V^T
    exp(-t L)   = V diag(exp(-t lambda))      V^T
    exp(-i t L) = V diag(exp(-i t lambda))    V^T
Only t is learnable (V, lambda are fixed per graph), so gradients flow to t.
"""

import torch
import torch.nn as nn


def normalized_adj(A: torch.Tensor) -> torch.Tensor:
    """A_hat = D^{-1/2}(A+I)D^{-1/2} (self-loops added), float64."""
    n = A.shape[0]
    A_tilde = A + torch.eye(n, dtype=A.dtype)
    deg = A_tilde.sum(1)
    dinv = torch.diag(deg.pow(-0.5))
    return dinv @ A_tilde @ dinv


def laplacian_eig(A: torch.Tensor):
    """Return (lambda, V) of the symmetric normalized Laplacian of A."""
    n = A.shape[0]
    A_hat = normalized_adj(A)
    L = torch.eye(n, dtype=A.dtype) - A_hat
    L = 0.5 * (L + L.T)  # symmetrize against fp drift
    evals, evecs = torch.linalg.eigh(L)
    return evals, evecs


class _Base(nn.Module):
    def __init__(self, hidden=32, layers=3, in_dim=1):
        super().__init__()
        self.layers = layers
        self.inp = nn.Linear(in_dim, hidden).double()
        self.mix = nn.ModuleList(
            [nn.Linear(hidden, hidden).double() for _ in range(layers)]
        )
        self.out = nn.Linear(hidden, 1).double()
        self.act = nn.ReLU()

    def prop(self, H, ctx):
        raise NotImplementedError

    def forward(self, X, ctx):
        # X: (B, n, in_dim) batched over destinations
        H = self.act(self.inp(X))
        for li in range(self.layers):
            H = self.act(self.mix[li](self.prop(H, ctx, li)))
        return self.out(H).squeeze(-1)  # (B, n)


class GCN(_Base):
    """Local 1-hop propagation; needs depth >= distance to carry information."""

    name = "GCN"

    def prop(self, H, ctx, li):
        return torch.einsum("nm,bmd->bnd", ctx["A_hat"], H)


class HeatGNN(_Base):
    """Global classical-diffusion propagation exp(-t L) (real)."""

    name = "Heat"

    def __init__(self, **kw):
        super().__init__(**kw)
        # one positive scale t per layer (softplus-parameterized)
        self.raw_t = nn.Parameter(torch.zeros(self.layers, dtype=torch.float64))

    def prop(self, H, ctx, li):
        t = torch.nn.functional.softplus(self.raw_t[li]) + 1e-3
        filt = torch.exp(-t * ctx["evals"])              # (n,)
        V = ctx["evecs"]
        proj = torch.einsum("nm,bmd->bnd", V.T, H)       # (B, n, d)
        proj = filt.view(1, -1, 1) * proj
        return torch.einsum("nm,bmd->bnd", V, proj)


class QWGNN(_Base):
    """Global quantum-walk propagation | exp(-i t L) H | (ballistic, interfering)."""

    name = "QW"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.raw_t = nn.Parameter(torch.zeros(self.layers, dtype=torch.float64))

    def prop(self, H, ctx, li):
        t = torch.nn.functional.softplus(self.raw_t[li]) + 1e-3
        phase = torch.exp(-1j * t * ctx["evals"].to(torch.complex128))  # (n,)
        V = ctx["evecs"].to(torch.complex128)
        Hc = H.to(torch.complex128)
        proj = torch.einsum("nm,bmd->bnd", V.conj().T, Hc)   # (B, n, d) complex
        proj = phase.view(1, -1, 1) * proj
        prop = torch.einsum("nm,bmd->bnd", V, proj)
        return prop.abs()  # measurement probability amplitude (real, >=0)


def build_ctx(A: torch.Tensor):
    """Precompute everything the operators need for one graph."""
    evals, evecs = laplacian_eig(A)
    return {"A": A, "A_hat": normalized_adj(A), "evals": evals, "evecs": evecs}


def count_params(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters())
