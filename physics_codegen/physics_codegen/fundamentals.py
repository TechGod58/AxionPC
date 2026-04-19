from __future__ import annotations

import json

FUNDAMENTALS = [
    {"domain": "Kinematics", "name": "Velocity", "equation": "v = dx/dt", "code_shape": "v = (x[i] - x[i-1]) / dt"},
    {"domain": "Kinematics", "name": "Acceleration", "equation": "a = dv/dt", "code_shape": "a = (v[i] - v[i-1]) / dt"},
    {"domain": "Dynamics", "name": "Newton's 2nd Law", "equation": "F = m*a", "code_shape": "a = F / m"},
    {"domain": "Energy", "name": "Kinetic Energy", "equation": "K = 1/2 m v^2", "code_shape": "K = 0.5 * m * v**2"},
    {"domain": "Energy", "name": "Potential Energy (gravity)", "equation": "U = m g h", "code_shape": "U = m * g * h"},
    {"domain": "Waves", "name": "Wave Speed", "equation": "c = f * lambda", "code_shape": "c = f * lam"},
    {"domain": "Waves", "name": "1D Wave PDE", "equation": "u_tt = c^2 u_xx", "code_shape": "u_next[i] = 2*u[i]-u_prev[i] + (c*dt/dx)**2*(u[i+1]-2*u[i]+u[i-1])"},
    {"domain": "Diffusion", "name": "Heat / Diffusion PDE", "equation": "u_t = D u_xx", "code_shape": "u_next[i] = u[i] + D*dt/dx**2*(u[i+1]-2*u[i]+u[i-1])"},
    {"domain": "Electrostatics", "name": "Poisson Equation", "equation": "nabla^2 phi = -rho/eps", "code_shape": "phi[i,j] = 0.25*(phi[i+1,j]+phi[i-1,j]+phi[i,j+1]+phi[i,j-1] + rhs)"},
    {"domain": "Fluids", "name": "Continuity (incompressible)", "equation": "div(u)=0", "code_shape": "project_velocity_field()"},
]


def as_json() -> str:
    return json.dumps(FUNDAMENTALS, indent=2, ensure_ascii=False)


def as_markdown_table() -> str:
    lines = [
        "| Domain | Concept | Equation | Code Shape |",
        "|---|---|---|---|",
    ]
    for row in FUNDAMENTALS:
        lines.append(f"| {row['domain']} | {row['name']} | `{row['equation']}` | `{row['code_shape']}` |")
    return "\n".join(lines)
