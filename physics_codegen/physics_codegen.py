#!/usr/bin/env python3
"""
physics_codegen: Engineering-focused Physics-to-Code Generator (MVP)

What it does (MVP):
- Reads a problem spec (YAML or JSON)
- Selects a governing equation template (currently: 1D wave, 2D incompressible Navier–Stokes (toy), 2D electrostatics Poisson)
- Emits a runnable Python/Numpy solver skeleton with stability hints

Design goals:
- Deterministic, auditable output
- No "magic" ML; explicit templates and checks
- Extendable: add templates in TEMPLATE_REGISTRY

Usage:
    python -m physics_codegen.cli generate --spec specs/wave_1d.yaml --out generated/
    python -m physics_codegen.cli list-templates
"""

from __future__ import annotations

__all__ = ["load_spec", "generate", "list_templates", "SpecError"]

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


class SpecError(ValueError):
    pass


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_spec(path: str) -> Dict[str, Any]:
    """Load YAML or JSON spec."""
    if not os.path.isfile(path):
        raise SpecError(f"Spec file not found: {path}")

    text = _read_text(path)
    ext = os.path.splitext(path)[1].lower()

    if ext in (".yaml", ".yml"):
        if yaml is None:
            raise SpecError("pyyaml not installed; use JSON spec or install pyyaml")
        data = yaml.safe_load(text)
    elif ext == ".json":
        data = json.loads(text)
    else:
        # Try YAML first, then JSON
        if yaml is not None:
            try:
                data = yaml.safe_load(text)
            except Exception:
                data = json.loads(text)
        else:
            data = json.loads(text)

    if not isinstance(data, dict):
        raise SpecError("Spec must be a mapping/object at top-level")
    return data


def _require(spec: Dict[str, Any], key: str, typ: tuple, ctx: str = "") -> Any:
    if key not in spec:
        raise SpecError(f"Missing required key '{key}'{': '+ctx if ctx else ''}")
    val = spec[key]
    if not isinstance(val, typ):
        raise SpecError(f"Key '{key}' must be of type {typ}, got {type(val)}")
    return val


def _get(spec: Dict[str, Any], key: str, typ: tuple, default: Any) -> Any:
    if key not in spec:
        return default
    val = spec[key]
    if not isinstance(val, typ):
        raise SpecError(f"Key '{key}' must be of type {typ}, got {type(val)}")
    return val


@dataclass(frozen=True)
class Template:
    name: str
    description: str
    validator: Any  # (spec)->normalized_spec
    renderer: Any   # (normalized_spec)->{logical_name:(relpath, code)}


def list_templates() -> Dict[str, str]:
    return {k: v.description for k, v in TEMPLATE_REGISTRY.items()}


def generate(spec: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """Return mapping: logical_name -> (relative_path, code_text)."""
    template_name = _require(spec, "template", (str,), "Top-level")
    if template_name not in TEMPLATE_REGISTRY:
        raise SpecError(
            f"Unknown template '{template_name}'. Available: {', '.join(sorted(TEMPLATE_REGISTRY))}"
        )
    tpl = TEMPLATE_REGISTRY[template_name]
    normalized = tpl.validator(spec)
    return tpl.renderer(normalized)


# ------------------------------
# Template: 1D Wave Equation
# u_tt = c^2 u_xx with optional damping gamma u_t
# Explicit leapfrog-like scheme
# ------------------------------
def _validate_wave_1d(spec: Dict[str, Any]) -> Dict[str, Any]:
    domain = _require(spec, "domain", (dict,), "wave_1d.domain")
    L = float(_require(domain, "L", (int, float), "domain length"))
    nx = int(_require(domain, "nx", (int,), "grid points"))
    if L <= 0 or nx < 3:
        raise SpecError("domain.L must be > 0 and domain.nx >= 3")

    params = _require(spec, "params", (dict,), "wave_1d.params")
    c = float(_require(params, "c", (int, float), "wave speed"))
    gamma = float(_get(params, "gamma", (int, float), 0.0))
    if c <= 0:
        raise SpecError("params.c must be > 0")
    if gamma < 0:
        raise SpecError("params.gamma must be >= 0")

    time = _require(spec, "time", (dict,), "wave_1d.time")
    t_end = float(_require(time, "t_end", (int, float), "end time"))
    dt = float(_require(time, "dt", (int, float), "time step"))
    if t_end <= 0 or dt <= 0:
        raise SpecError("time.t_end and time.dt must be > 0")

    bcs = _get(spec, "bcs", (dict,), {})
    bc_type = str(_get(bcs, "type", (str,), "dirichlet")).lower()
    if bc_type not in ("dirichlet", "neumann"):
        raise SpecError("bcs.type must be 'dirichlet' or 'neumann'")

    ic = _get(spec, "initial_conditions", (dict,), {})
    ic_type = str(_get(ic, "type", (str,), "gaussian")).lower()
    if ic_type not in ("gaussian", "sine", "file"):
        raise SpecError("initial_conditions.type must be gaussian|sine|file")

    dx = L / (nx - 1)
    cfl = c * dt / dx  # stability hint for wave
    return {
        "template": "wave_1d",
        "domain": {"L": L, "nx": nx, "dx": dx},
        "params": {"c": c, "gamma": gamma, "cfl": cfl},
        "time": {"t_end": t_end, "dt": dt, "nt": int(math.ceil(t_end / dt))},
        "bcs": {"type": bc_type},
        "initial_conditions": {"type": ic_type, **ic},
        "meta": _get(spec, "meta", (dict,), {}),
    }


def _render_wave_1d(spec: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    L = spec["domain"]["L"]
    nx = spec["domain"]["nx"]
    dx = spec["domain"]["dx"]
    c = spec["params"]["c"]
    gamma = spec["params"]["gamma"]
    dt = spec["time"]["dt"]
    t_end = spec["time"]["t_end"]
    bc_type = spec["bcs"]["type"]
    ic = spec["initial_conditions"]

    code = f'''#!/usr/bin/env python3
"""
Generated solver: 1D Wave Equation (explicit)

PDE:
    u_tt = c^2 u_xx - 2*gamma*u_t   (gamma >= 0; if gamma=0 it's undamped)

Numerics:
    - second-order central differences in space
    - explicit time stepping (leapfrog-like)

Stability (linear):
    CFL = c*dt/dx <= 1 is required for stability in the undamped case.

This file is generated by physics_codegen.
"""

from __future__ import annotations

import math
import numpy as np

def init_u(x: np.ndarray) -> np.ndarray:
    typ = {json.dumps(ic.get("type","gaussian"))}
    if typ == "gaussian":
        x0 = float({ic.get("x0", 0.5*L)})
        sigma = float({ic.get("sigma", 0.05*L)})
        amp = float({ic.get("amplitude", 1.0)})
        return amp * np.exp(-0.5*((x-x0)/sigma)**2)
    if typ == "sine":
        k = float({ic.get("k", math.pi*2/L)})
        amp = float({ic.get("amplitude", 1.0)})
        return amp * np.sin(k*x)
    if typ == "file":
        path = {json.dumps(ic.get("path","u0.npy"))}
        arr = np.load(path)
        if arr.shape != x.shape:
            raise ValueError(f"u0 from {{path}} has shape {{arr.shape}}, expected {{x.shape}}")
        return arr
    raise ValueError("Unknown initial condition type")

def apply_bcs(u: np.ndarray) -> None:
    if {json.dumps(bc_type)} == "dirichlet":
        u[0] = 0.0
        u[-1] = 0.0
    elif {json.dumps(bc_type)} == "neumann":
        u[0] = u[1]
        u[-1] = u[-2]
    else:
        raise ValueError("Unsupported BC")

def step(u: np.ndarray, u_prev: np.ndarray, c: float, gamma: float, dx: float, dt: float) -> np.ndarray:
    u_next = np.empty_like(u)
    r2 = (c*dt/dx)**2
    u_next[1:-1] = (2*u[1:-1] - u_prev[1:-1]
                    + r2*(u[2:] - 2*u[1:-1] + u[:-2])
                    - 2*gamma*dt*(u[1:-1] - u_prev[1:-1]))
    # boundary placeholders; BC applied after
    u_next[0] = u_next[1]
    u_next[-1] = u_next[-2]
    apply_bcs(u_next)
    return u_next

def run():
    L = float({L})
    nx = int({nx})
    dx = float({dx})
    c = float({c})
    gamma = float({gamma})
    dt = float({dt})
    t_end = float({t_end})

    cfl = c*dt/dx
    print(f"dx={{dx:.6g}}, dt={{dt:.6g}}, CFL={{cfl:.6g}} (require <= 1 for stability in undamped case)")
    if cfl > 1.0:
        print("WARNING: CFL > 1; expect instability unless you change dt or nx.")

    x = np.linspace(0.0, L, nx)
    u0 = init_u(x)

    # assume initial velocity u_t(x,0)=0
    u_prev = u0.copy()
    u = u0.copy()
    apply_bcs(u_prev)
    apply_bcs(u)

    t = 0.0
    out_every = max(1, int(round(0.01/dt)))  # every ~0.01 s
    snapshots = []
    times = []
    nsteps = int(math.ceil(t_end/dt))
    for n in range(nsteps):
        u_next = step(u, u_prev, c=c, gamma=gamma, dx=dx, dt=dt)
        u_prev, u = u, u_next
        t += dt

        if n % out_every == 0 or n == nsteps-1:
            snapshots.append(u.copy())
            times.append(t)

    snapshots = np.stack(snapshots, axis=0)
    times = np.array(times)
    np.save("u_snapshots.npy", snapshots)
    np.save("t_snapshots.npy", times)
    print("Saved u_snapshots.npy and t_snapshots.npy")

if __name__ == "__main__":
    run()
'''
    return {"solver": ("generated/wave_1d_solver.py", code)}


# ------------------------------
# Template: 2D Electrostatics (Poisson)
# ∇^2 V = -rho/epsilon  (constant epsilon in MVP)
# Gauss–Seidel
# ------------------------------
def _validate_poisson_2d(spec: Dict[str, Any]) -> Dict[str, Any]:
    domain = _require(spec, "domain", (dict,), "poisson_2d.domain")
    Lx = float(_require(domain, "Lx", (int, float), "Lx"))
    Ly = float(_require(domain, "Ly", (int, float), "Ly"))
    nx = int(_require(domain, "nx", (int,), "nx"))
    ny = int(_require(domain, "ny", (int,), "ny"))
    if Lx <= 0 or Ly <= 0 or nx < 3 or ny < 3:
        raise SpecError("domain sizes must be >0 and nx,ny >=3")
    dx = Lx/(nx-1)
    dy = Ly/(ny-1)

    params = _require(spec, "params", (dict,), "poisson_2d.params")
    eps = float(_get(params, "epsilon", (int, float), 1.0))
    if eps <= 0:
        raise SpecError("params.epsilon must be > 0")

    solver = _get(spec, "solver", (dict,), {})
    max_iter = int(_get(solver, "max_iter", (int,), 10000))
    tol = float(_get(solver, "tol", (int, float), 1e-6))

    bcs = _require(spec, "bcs", (dict,), "poisson_2d.bcs")
    if str(_get(bcs, "type", (str,), "dirichlet")).lower() != "dirichlet":
        raise SpecError("poisson_2d MVP supports only dirichlet bcs")
    V_left = float(_get(bcs, "V_left", (int, float), 0.0))
    V_right = float(_get(bcs, "V_right", (int, float), 0.0))
    V_bottom = float(_get(bcs, "V_bottom", (int, float), 0.0))
    V_top = float(_get(bcs, "V_top", (int, float), 0.0))

    rho = _get(spec, "charge_density", (dict,), {"type": "zero"})
    rho_type = str(_get(rho, "type", (str,), "zero")).lower()
    if rho_type not in ("zero", "point"):
        raise SpecError("charge_density.type must be zero|point")

    return {
        "template": "poisson_2d",
        "domain": {"Lx": Lx, "Ly": Ly, "nx": nx, "ny": ny, "dx": dx, "dy": dy},
        "params": {"epsilon": eps},
        "solver": {"max_iter": max_iter, "tol": tol},
        "bcs": {"type": "dirichlet", "V_left": V_left, "V_right": V_right, "V_bottom": V_bottom, "V_top": V_top},
        "charge_density": rho,
        "meta": _get(spec, "meta", (dict,), {}),
    }


def _render_poisson_2d(spec: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    d = spec["domain"]
    b = spec["bcs"]
    eps = spec["params"]["epsilon"]
    solver = spec["solver"]
    rho_cfg = spec["charge_density"]

    code = f'''#!/usr/bin/env python3
"""
Generated solver: 2D Electrostatics (Poisson)

Equation (constant epsilon in MVP):
    ∇^2 V = -rho/epsilon

Numerics:
    - 5-point stencil
    - Gauss–Seidel iteration

Outputs:
    V.npy, Ex.npy, Ey.npy  where E = -∇V
"""

from __future__ import annotations

import numpy as np

def build_rho(nx: int, ny: int, dx: float, dy: float) -> np.ndarray:
    rho = np.zeros((ny, nx), dtype=float)
    cfg = {json.dumps(rho_cfg)}
    typ = cfg.get("type", "zero")
    if typ == "zero":
        return rho
    if typ == "point":
        ix = int(cfg.get("ix", nx//2))
        iy = int(cfg.get("iy", ny//2))
        q = float(cfg.get("q", 1.0))
        rho[iy, ix] = q/(dx*dy)
        return rho
    raise ValueError("Unsupported rho type")

def apply_dirichlet(V: np.ndarray) -> None:
    V[:, 0] = {b["V_left"]}
    V[:, -1] = {b["V_right"]}
    V[0, :] = {b["V_bottom"]}
    V[-1, :] = {b["V_top"]}

def solve_poisson(nx: int, ny: int, dx: float, dy: float, epsilon: float, max_iter: int, tol: float) -> np.ndarray:
    V = np.zeros((ny, nx), dtype=float)
    rho = build_rho(nx, ny, dx, dy)
    apply_dirichlet(V)

    dx2 = dx*dx
    dy2 = dy*dy
    denom = 2*(dx2 + dy2)

    for it in range(max_iter):
        V_old = V.copy()
        for j in range(1, ny-1):
            for i in range(1, nx-1):
                V[j, i] = ((V[j, i+1] + V[j, i-1])*dy2 + (V[j+1, i] + V[j-1, i])*dx2 + (rho[j, i]/epsilon)*dx2*dy2) / denom
        apply_dirichlet(V)
        err = np.max(np.abs(V - V_old))
        if it % 200 == 0:
            print(f"iter={{it}}, max|dV|={{err:.3e}}")
        if err < tol:
            print(f"Converged in {{it}} iterations, max|dV|={{err:.3e}}")
            break
    else:
        print(f"Reached max_iter={{max_iter}} with max|dV|={{err:.3e}}")

    return V

def compute_E(V: np.ndarray, dx: float, dy: float):
    Ey, Ex = np.gradient(V, dy, dx)
    return -Ex, -Ey

def run():
    Lx, Ly = {d["Lx"]}, {d["Ly"]}
    nx, ny = int({d["nx"]}), int({d["ny"]})
    dx, dy = Lx/(nx-1), Ly/(ny-1)
    epsilon = float({eps})
    max_iter = int({solver["max_iter"]})
    tol = float({solver["tol"]})

    V = solve_poisson(nx, ny, dx, dy, epsilon, max_iter, tol)
    Ex, Ey = compute_E(V, dx, dy)
    np.save("V.npy", V)
    np.save("Ex.npy", Ex)
    np.save("Ey.npy", Ey)
    print("Saved V.npy, Ex.npy, Ey.npy")

if __name__ == "__main__":
    run()
'''
    return {"solver": ("generated/poisson_2d_solver.py", code)}


# ------------------------------
# Template: 2D Incompressible Navier–Stokes (toy)
# Projection method, educational skeleton
# ------------------------------
def _validate_ns2d_incompressible(spec: Dict[str, Any]) -> Dict[str, Any]:
    domain = _require(spec, "domain", (dict,), "ns2d.domain")
    Lx = float(_require(domain, "Lx", (int, float), "Lx"))
    Ly = float(_require(domain, "Ly", (int, float), "Ly"))
    nx = int(_require(domain, "nx", (int,), "nx"))
    ny = int(_require(domain, "ny", (int,), "ny"))
    if Lx <= 0 or Ly <= 0 or nx < 8 or ny < 8:
        raise SpecError("domain sizes must be >0 and nx,ny >= 8 for ns2d template")
    dx = Lx/(nx-1)
    dy = Ly/(ny-1)

    params = _require(spec, "params", (dict,), "ns2d.params")
    rho = float(_require(params, "rho", (int, float), "density"))
    nu = float(_require(params, "nu", (int, float), "kinematic viscosity"))
    if rho <= 0 or nu < 0:
        raise SpecError("params.rho must be >0 and params.nu >= 0")

    time = _require(spec, "time", (dict,), "ns2d.time")
    dt = float(_require(time, "dt", (int, float), "dt"))
    t_end = float(_require(time, "t_end", (int, float), "t_end"))
    if dt <= 0 or t_end <= 0:
        raise SpecError("time.dt and time.t_end must be > 0")

    dt_diff = float("inf") if nu == 0 else min(dx*dx, dy*dy)/(4*nu)

    return {
        "template": "ns2d_incompressible",
        "domain": {"Lx": Lx, "Ly": Ly, "nx": nx, "ny": ny, "dx": dx, "dy": dy},
        "params": {"rho": rho, "nu": nu, "dt_diff_limit": dt_diff},
        "time": {"dt": dt, "t_end": t_end, "nt": int(math.ceil(t_end/dt))},
        "meta": _get(spec, "meta", (dict,), {}),
    }


def _render_ns2d_incompressible(spec: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    d = spec["domain"]
    p = spec["params"]
    t = spec["time"]

    code = f'''#!/usr/bin/env python3
"""
Generated solver: 2D Incompressible Navier–Stokes (toy)

Equations:
    u_t + u·∇u = -1/rho ∇p + nu ∇^2 u
    ∇·u = 0

Numerics:
    - Semi-explicit "stable fluids" style projection (educational / engineering sketch)
    - Not production CFD.

Outputs:
    u.npy, v.npy, p.npy
"""

from __future__ import annotations

import numpy as np

def divergence(u, v, dx, dy):
    return (u[1:-1,2:] - u[1:-1,:-2])/(2*dx) + (v[2:,1:-1] - v[:-2,1:-1])/(2*dy)

def gradient(p, dx, dy):
    dpdx = (p[1:-1,2:] - p[1:-1,:-2])/(2*dx)
    dpdy = (p[2:,1:-1] - p[:-2,1:-1])/(2*dy)
    return dpdx, dpdy

def laplacian(f, dx, dy):
    return (f[1:-1,2:] - 2*f[1:-1,1:-1] + f[1:-1,:-2])/(dx*dx) + (f[2:,1:-1] - 2*f[1:-1,1:-1] + f[:-2,1:-1])/(dy*dy)

def apply_bcs(u, v, p):
    u[0,:] = 0; u[-1,:] = 0; u[:,0] = 0; u[:,-1] = 0
    v[0,:] = 0; v[-1,:] = 0; v[:,0] = 0; v[:,-1] = 0
    p[0,:] = p[1,:]
    p[-1,:] = p[-2,:]
    p[:,0] = p[:,1]
    p[:,-1] = p[:,-2]

def pressure_poisson(p, u, v, dx, dy, iters):
    for _ in range(iters):
        p_old = p.copy()
        rhs = divergence(u, v, dx, dy)
        p[1:-1,1:-1] = ((p_old[1:-1,2:] + p_old[1:-1,:-2])*dy*dy +
                        (p_old[2:,1:-1] + p_old[:-2,1:-1])*dx*dx -
                        (dx*dx*dy*dy)*rhs) / (2*(dx*dx + dy*dy))
        apply_bcs(u, v, p)
    return p

def advect(u, v, dt, dx, dy):
    ny, nx = u.shape
    u0, v0 = u.copy(), v.copy()
    X, Y = np.meshgrid(np.arange(nx), np.arange(ny))

    x = X - (dt/dx)*u0
    y = Y - (dt/dy)*v0
    x = np.clip(x, 0, nx-1)
    y = np.clip(y, 0, ny-1)

    x0 = x.astype(int); y0 = y.astype(int)
    x1 = np.minimum(x0+1, nx-1); y1 = np.minimum(y0+1, ny-1)
    sx = x - x0; sy = y - y0

    def sample(f):
        f00 = f[y0, x0]
        f10 = f[y0, x1]
        f01 = f[y1, x0]
        f11 = f[y1, x1]
        return (1-sx)*(1-sy)*f00 + sx*(1-sy)*f10 + (1-sx)*sy*f01 + sx*sy*f11

    u[:] = sample(u0)
    v[:] = sample(v0)
    return u, v

def diffuse(u, v, nu, dt, dx, dy):
    if nu == 0.0:
        return u, v
    u0, v0 = u.copy(), v.copy()
    u[1:-1,1:-1] = u0[1:-1,1:-1] + nu*dt*laplacian(u0, dx, dy)
    v[1:-1,1:-1] = v0[1:-1,1:-1] + nu*dt*laplacian(v0, dx, dy)
    return u, v

def add_forcing(u, v, dt):
    ny, nx = u.shape
    cx, cy = nx//2, ny//2
    v[cy-2:cy+2, cx-2:cx+2] += 10.0*dt
    return u, v

def run():
    Lx, Ly = {d["Lx"]}, {d["Ly"]}
    nx, ny = int({d["nx"]}), int({d["ny"]})
    dx, dy = Lx/(nx-1), Ly/(ny-1)
    rho = float({p["rho"]})
    nu = float({p["nu"]})
    dt = float({t["dt"]})
    t_end = float({t["t_end"]})

    dt_diff_limit = {p["dt_diff_limit"]}
    if nu > 0 and dt > dt_diff_limit:
        print(f"WARNING: dt={{dt}} > diffusion stability hint {{dt_diff_limit}}")

    u = np.zeros((ny, nx), dtype=float)
    v = np.zeros((ny, nx), dtype=float)
    pfield = np.zeros((ny, nx), dtype=float)
    apply_bcs(u, v, pfield)

    steps = int(np.ceil(t_end/dt))
    for n in range(steps):
        u, v = add_forcing(u, v, dt)
        u, v = advect(u, v, dt, dx, dy)
        u, v = diffuse(u, v, nu, dt, dx, dy)

        pfield = pressure_poisson(pfield, u, v, dx, dy, iters=80)
        dpdx, dpdy = gradient(pfield, dx, dy)

        u[1:-1,1:-1] -= (dt/rho)*dpdx
        v[1:-1,1:-1] -= (dt/rho)*dpdy
        apply_bcs(u, v, pfield)

        if n % max(1, steps//10) == 0:
            rhs = divergence(u, v, dx, dy)
            print(f"step {{n}}/{{steps}}, max|div|={{np.max(np.abs(rhs)):.3e}}")

    np.save("u.npy", u)
    np.save("v.npy", v)
    np.save("p.npy", pfield)
    print("Saved u.npy, v.npy, p.npy")

if __name__ == "__main__":
    run()
'''
    return {"solver": ("generated/ns2d_incompressible_solver.py", code)}


TEMPLATE_REGISTRY = {
    "wave_1d": Template(
        name="wave_1d",
        description="1D wave equation u_tt = c^2 u_xx with optional damping; explicit scheme.",
        validator=_validate_wave_1d,
        renderer=_render_wave_1d,
    ),
    "poisson_2d": Template(
        name="poisson_2d",
        description="2D electrostatics Poisson solver ∇^2 V = -rho/epsilon (constant ε); Gauss–Seidel.",
        validator=_validate_poisson_2d,
        renderer=_render_poisson_2d,
    ),
    "ns2d_incompressible": Template(
        name="ns2d_incompressible",
        description="2D incompressible Navier–Stokes (toy) projection method; educational skeleton.",
        validator=_validate_ns2d_incompressible,
        renderer=_render_ns2d_incompressible,
    ),
}
