| Domain | Concept | Equation | Code Shape |
|---|---|---|---|
| Kinematics | Velocity | `v = dx/dt` | `v = (x[i] - x[i-1]) / dt` |
| Kinematics | Acceleration | `a = dv/dt` | `a = (v[i] - v[i-1]) / dt` |
| Dynamics | Newton's 2nd Law | `F = m*a` | `a = F / m` |
| Energy | Kinetic Energy | `K = 1/2 m v^2` | `K = 0.5 * m * v**2` |
| Energy | Potential Energy (gravity) | `U = m g h` | `U = m * g * h` |
| Waves | Wave Speed | `c = f * lambda` | `c = f * lam` |
| Waves | 1D Wave PDE | `u_tt = c^2 u_xx` | `u_next[i] = 2*u[i]-u_prev[i] + (c*dt/dx)**2*(u[i+1]-2*u[i]+u[i-1])` |
| Diffusion | Heat / Diffusion PDE | `u_t = D u_xx` | `u_next[i] = u[i] + D*dt/dx**2*(u[i+1]-2*u[i]+u[i-1])` |
| Electrostatics | Poisson Equation | `nabla^2 phi = -rho/eps` | `phi[i,j] = 0.25*(phi[i+1,j]+phi[i-1,j]+phi[i,j+1]+phi[i,j-1] + rhs)` |
| Fluids | Continuity (incompressible) | `div(u)=0` | `project_velocity_field()` |
