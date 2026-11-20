# EIT algorithm and discrete derivatives

The public reconstruction algorithm is `lbfgsb_tv`: P1 FEM + exact discrete adjoint + bounded L-BFGS-B + smoothed isotropic TV. Boundary-model choices (`cem`, `continuum`) and data modes (`difference`, `absolute`) are settings of this one non-learning method.

Classical background: [Jin & Maass (2012)](https://doi.org/10.1051/cocv/2011193) and [Gehre, Jin & Lu (2014)](https://arxiv.org/abs/1312.1390). The particular normalization, calibration procedure, geometry, thickness treatment, and default hyperparameters describe this implementation, rather than a parameter-for-parameter reproduction of either publication.

## 1. Physical model

Let Ω be the 2D domain, h its thickness in m, σ its positive scalar conductivity in S/m, u the interior potential in V, U_l the electrode potential, and z_l the physical contact impedance in Ω·m². The volume equation is

\[
\nabla\cdot(\sigma\nabla u)=0.
\]

The complete electrode model (CEM) prescribes

\[
u+z_l\sigma\partial_nu=U_l\quad\text{on }e_l,
\qquad h\int_{e_l}\sigma\partial_nu\,ds=I_l,
\]

with zero normal current on electrode gaps. Currents satisfy \(\sum_l I_l=0\); the gauge is \(\sum_l U_l=0\). The weak form is

\[
h\int_\Omega\sigma\nabla u\cdot\nabla v\,dx+
\sum_l\frac{h}{z_l}\int_{e_l}(u-U_l)(v-V_l)\,ds
=\sum_l I_lV_l.
\]

Thickness enters both volume and contact terms. Each electrode has finite boundary extent and its own unknown equipotential value; it is not represented by a single mesh node.

The continuum Neumann model prescribes the sheet flux \(g=h\sigma\partial_nu\), in A/m:

\[
\int_{\partial\Omega}g\,ds=0,\qquad
h\int_\Omega\sigma\nabla u\cdot\nabla v\,dx=
\int_{\partial\Omega}gv\,ds,\qquad
\int_{\partial\Omega}u\,ds=0.
\]

For finite-electrode experimental data the continuum variant uses
\(g=\sum_l I_l\chi_{e_l}/|e_l|\) and observes region averages
\(\bar u_l=|e_l|^{-1}\int_{e_l}u\,ds\). Gaps have zero flux. This prescribed-flux approximation has neither contact impedance nor electrode equipotential constraints. It is not CEM with `z=0`.

`ForwardModel.continuum_flux(sigma, nodal_flux)` also accepts a general compatible P1 boundary flux, allowing a smooth-flux forward experiment independent of the finite-electrode measurement protocol.

## 2. P1 finite elements

Both u and σ use continuous piecewise-linear nodal basis functions φ_i. On triangle t, with area A_t and constant basis gradient b_ti, the element stiffness is

\[
K^t_{ij}=h A_t\frac{\sigma_{t1}+\sigma_{t2}+\sigma_{t3}}{3}
b_{ti}\cdot b_{tj}.
\]

The nodal mean is the exact integral average of a linear conductivity on a triangle. A boundary edge of length ℓ has mass matrix \(\ell[[2,1],[1,2]]/6\) and integral vector \(\ell[1,1]/2\). The local CEM contribution on endpoints a,b and electrode l is

\[
\frac{h\ell}{6z_l}
\begin{bmatrix}2&1&-3\\1&2&-3\\-3&-3&6\end{bmatrix}.
\]

Adding the gauge multiplier gives the sparse symmetric saddle system

\[
\begin{bmatrix}K+C&B&0\\B^T&D&\mathbf1\\0&\mathbf1^T&0\end{bmatrix}
\begin{bmatrix}u\\U\\\eta\end{bmatrix}=
\begin{bmatrix}0\\I\\0\end{bmatrix}.
\]

For continuum observations the system is \([K,c;c^T,0][u,\eta]^T=[b_g,0]^T\), with \(c_i=\int_{\partial\Omega}\phi_i ds\). A sparse LU factorization is shared by all current-pattern right-hand sides in one solve.

The voltage matrix is `M @ U` in CEM and `M @ electrode_average(u)` in the continuum approximation. Each row of M sums to zero, making voltage differences gauge invariant. The code rejects incompatible current patterns rather than balancing them through the gauge multiplier.

## 3. Reference-only calibration

Before target reconstruction, fit a homogeneous conductivity σ_bg to all available homogeneous reference voltages. CEM additionally fits each electrode's z_l. No target measurement, photograph, target location, or material label enters this calibration. The continuum variant fits σ_bg only.

The parameters are optimized in logarithmic coordinates using normalized least squares and L-BFGS-B. The initial values are read from the input. Calibration bounds are `[0.001, 0.3] S/m` and `[1e-7, 0.1] Ω·m²`; the default iteration limit is 400, `ftol=1e-13`, and `gtol=1e-8`. These are implementation settings. The fitted contacts are effective model parameters and are not independent experimental measurements of physical contact impedance.

The target step keeps σ_bg and z fixed. Both inversion modes currently require reference measurements for this initial calibration.

## 4. Data objective and smoothed TV

Optimize relative conductivity \(m=\sigma/\sigma_{bg}\), initialized uniformly to 1 and bounded by `lower <= m <= upper`. Let W be the Boolean measurement mask; retained channels have equal weight.

In difference mode,

\[
d=V_{target}-V_{reference},\qquad
r(m)=F(\sigma_{bg}m)-F(\sigma_{bg})-d.
\]

This is a nonlinear difference prediction. The measured voltage difference is not treated as absolute voltage. In absolute mode, \(d=V_{target}\) and \(r(m)=F(\sigma_{bg}m)-d\).

The normalized objective is

\[
J(m)=\frac{\|Wr(m)\|_2^2}{2\|Wd\|_2^2}+
\alpha\sum_t A_t\left(\sqrt{|\nabla m|_t^2+\epsilon^2}-\epsilon\right).
\]

When \(\|Wd\|_2^2<10^{-24}\), use \(\|WV_{reference}\|_2^2\) instead, so an unchanged target remains admissible. The fallback uses the same retained channels W, whereas reference calibration fits the complete reference array. The selected denominator is recorded as `metadata.voltage_normalization_source` in `run.json`; an unusable fallback norm is rejected. Use this selected denominator in the adjoint equation below as well.

This is smoothed, isotropic, geometrical FEM TV. It is neither a graph-edge penalty nor nonsmooth TV. Relative conductivity is dimensionless; ∇m and ε have units m⁻¹, the TV integral has units m, and α has units m⁻¹. A change from meter coordinates requires consistent adjustment of α and ε. The constant `-epsilon` does not affect gradients.

The default values are `alpha=0.03`, `tv_epsilon=0.1`, bounds `[0.05,5]`, `ftol=1e-8`, `gtol=1e-6`, and 500 target iterations. They are a uniform baseline from the supplied material. Absolute mode has a different normalization, so α should be selected separately; the original absolute demonstration used `0.0003`.

## 5. Exact discrete adjoint

Write the state system for pattern p as \(A(\sigma)x_p=b_p\), and predictions as \(Hx_p\). Set

\[
q_p=\frac{W^TW r_p}{\|Wd\|_2^2},\qquad
A(\sigma)^T p_p=H^Tq_p.
\]

Implicit differentiation gives the negative sign

\[
\frac{\partial J_{data}}{\partial\sigma_i}
=-\sum_p p_p^T\frac{\partial A}{\partial\sigma_i}x_p
=-h\sum_p\int_\Omega\phi_i\nabla u_p\cdot\nabla p_p\,dx.
\]

Each neighboring element contributes \(-h A_t\sum_p\nabla u_{tp}\cdot\nabla p_{tp}/3\) to each of its three conductivity nodes. The implementation contracts element gradients and accumulates node contributions without forming a full sensitivity matrix.

For relative conductivity, apply the chain rule and add TV:

\[
\frac{\partial J}{\partial m_i}=
\sigma_{bg}\frac{\partial J_{data}}{\partial\sigma_i}+
\alpha\sum_{t\ni i}A_t
\frac{\nabla m|_t\cdot b_{ti}}{\sqrt{|\nabla m|_t^2+\epsilon^2}}.
\]

Calibration uses \(\partial J/\partial\log\sigma_{bg}=\sigma_{bg}\sum_i\partial J/\partial\sigma_i\). For CEM contacts,

\[
\frac{\partial J}{\partial\log z_l}=
\frac{h}{z_l}\sum_p\int_{e_l}(u_p-U_{lp})(p_p-P_{lp})\,ds.
\]

Its positive sign follows from \(\partial A_{contact}/\partial\log z=-A_{contact}\). Finite differences are used for validation, not for optimization gradients.

## 6. Stopping, budgets, and interpretation

L-BFGS-B solves a nonconvex bounded optimization problem; its termination does not establish uniqueness or image accuracy. The run records the optimizer status, actual iterations, objective history, bound-hit fractions, and explicit stopping reason. A reached iteration cap is not labeled convergence.

Forward and adjoint budgets count batched solves during calibration, baseline prediction, and reconstruction. Elapsed-time limits are cooperative between work units. A stopped run keeps only fully evaluated accepted optimizer iterates, and does not promote an unfinished line-search trial or a calibrated background to a reconstructed target.

Verification should check system residuals, reciprocity, CEM recovered-current conservation and gauge, continuum gauge and disk analytic solution with refinement, directional derivatives for pure data and full TV objectives, contact log-parameter derivatives, synthetic anomaly fit improvement, and rejection of incompatible currents. See [VALIDATION.md](VALIDATION.md) for the checks actually run.

Experimental data have no nodal or pixelwise conductivity truth. A photo can help assess object location visually, but cannot support conductivity PSNR/SSIM. Differences in geometry, finite mesh resolution, current-scale convention, effective contact layers, smoothed TV, and bounded contrast limit quantitative interpretation. Smaller difference residuals alone do not establish that one boundary model is more physically accurate, since each subtracts its own modeled background.
