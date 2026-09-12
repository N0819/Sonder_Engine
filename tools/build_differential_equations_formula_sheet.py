from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

OUT = "output/pdf/differential-equations-formula-sheet.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Title2", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18,
                          leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#17324d"), spaceAfter=5))
styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"], fontSize=8.5, leading=11, alignment=TA_CENTER,
                          textColor=colors.HexColor("#4b5966"), spaceAfter=10))
styles.add(ParagraphStyle(name="H", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12,
                          leading=14, textColor=colors.HexColor("#17324d"), spaceBefore=6, spaceAfter=5))
styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=7.25, leading=9))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=7.6, leading=9.5))
styles.add(ParagraphStyle(name="Foot", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=colors.HexColor("#53616d")))

def P(s, style="Cell"):
    return Paragraph(s, styles[style])

def section(title, rows, widths=(1.38*inch, 2.42*inch, 2.85*inch)):
    data = [[P("RELATION / TYPE"), P("RECOGNIZE &amp; STANDARD FORM"), P("METHOD / USE")]]
    data += [[P(a), P(b), P(c)] for a,b,c in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17324d")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.2),
        ("LEADING", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#b9c7d3")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f7f9")]),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    return [KeepTogether([Paragraph(title, styles["H"]), t]), Spacer(1, 7)]

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#b9c7d3")); canvas.line(0.55*inch, 0.47*inch, 7.95*inch, 0.47*inch)
    canvas.setFont("Helvetica", 6.5); canvas.setFillColor(colors.HexColor("#53616d"))
    canvas.drawString(0.55*inch, 0.31*inch, "Differential Equations Formula Sheet | Kreyszig, Advanced Engineering Mathematics (9th ed.)")
    canvas.drawRightString(7.95*inch, 0.31*inch, f"{doc.page}")
    canvas.restoreState()

story = [Paragraph("Differential Equations Formula Sheet", styles["Title2"]),
         Paragraph("Organized by relation and use | Definitions use x as the independent variable; primes denote d/dx.", styles["Sub"])]

story += section("1. Classify first; then choose the method", [
    ("Order / linearity", "Order = highest derivative. Linear: <b>a<sub>n</sub>y<sup>(n)</sup>+...+a<sub>0</sub>y=g(x)</b>; coefficients depend only on x, and y and derivatives occur to first power.", "Linearity permits superposition: y = y<sub>h</sub> + y<sub>p</sub>. Initial conditions select constants; boundary conditions select modes/coefficients."),
    ("Initial vs boundary value", "IVP: y(x<sub>0</sub>), y'(x<sub>0</sub>), ... given at one point. BVP: values/fluxes specified at endpoints or boundaries.", "IVPs model time evolution from a known state. BVPs model spatial equilibrium, vibrations, and diffusion in a bounded domain."),
    ("Autonomous first order", "<b>y' = f(y)</b> (no explicit x). Equilibria solve f(y*)=0; inspect the sign of f(y).", "Use a phase line for long-term behavior and stability; separate variables if an explicit solution is needed."),
])

story += section("2. First-order ODE relations", [
    ("Separable", "<b>y' = g(x)h(y)</b>. Rearrange: <b>dy/h(y) = g(x)dx</b>.", "Integrate both sides: ∫dy/h(y) = ∫g(x)dx + C. Use for growth/decay, logistic populations, falling bodies with simple drag."),
    ("Linear first order", "<b>y' + p(x)y = q(x)</b>. Integrating factor <b>μ(x)=e<sup>∫p dx</sup></b>.", "(μy)'=μq, so <b>y=μ<sup>-1</sup>[∫μq dx+C]</b>. Use for mixing, RC/RL circuits, Newton cooling, driven first-order processes."),
    ("Exact", "<b>M(x,y)dx+N(x,y)dy=0</b>; exact if <b>M<sub>y</sub>=N<sub>x</sub></b> on the domain.", "Find potential F with F<sub>x</sub>=M, F<sub>y</sub>=N; answer F(x,y)=C. Use when the relation is a conserved potential/total differential."),
    ("Integrating factor for nonexact", "For Mdx+Ndy=0, if (M<sub>y</sub>-N<sub>x</sub>)/N=f(x), then <b>μ=e<sup>∫f(x)dx</sup></b>. If (N<sub>x</sub>-M<sub>y</sub>)/M=g(y), then μ=e<sup>∫g(y)dy</sup>.", "Turns a nonexact equation exact. Check either ratio depends on one variable only."),
    ("Bernoulli", "<b>y'+p(x)y=q(x)y<sup>n</sup></b>, n≠0,1. Let <b>v=y<sup>1-n</sup></b>.", "Then v'+(1-n)pv=(1-n)q, a linear equation. Use for nonlinear growth/drag laws with one power of y."),
    ("Homogeneous (ratio form)", "<b>y'=F(y/x)</b> or M,N homogeneous of same degree. Let <b>v=y/x</b>, y=vx, y'=v+xv'.", "Becomes separable in v and x. Use when x and y appear only through their ratio or matching powers."),
    ("Riccati / reducible special case", "<b>y'=a(x)y²+b(x)y+c(x)</b>. If one particular solution y<sub>p</sub> is known, let y=y<sub>p</sub>+1/v.", "Reduces to a linear equation in v. Use only when a known solution or structure supplies y<sub>p</sub>; otherwise it is generally nonlinear."),
])

story.append(PageBreak())
story += section("3. Linear ODEs of order 2 and higher", [
    ("Homogeneous linear", "<b>a<sub>n</sub>y<sup>(n)</sup>+...+a<sub>0</sub>y=0</b>. n linearly independent solutions form y<sub>h</sub>=Σc<sub>i</sub>y<sub>i</sub>.", "Use superposition. Wronskian W≠0 at a point confirms independence (under standard continuity assumptions)."),
    ("Constant coefficients", "For <b>a<sub>n</sub>y<sup>(n)</sup>+...+a<sub>0</sub>y=g(x)</b>, solve characteristic polynomial P(r)=0 for y<sub>h</sub>.", "Root r gives e<sup>rx</sup>; multiplicity m gives x<sup>k</sup>e<sup>rx</sup>, k=0...m-1. Pair α±iβ gives e<sup>αx</sup>(C<sub>1</sub>cosβx+C<sub>2</sub>sinβx)."),
    ("Undetermined coefficients", "For constant-coefficient L[y]=g(x), with g a polynomial, e<sup>ax</sup>, sin bx/cos bx, or products.", "Guess y<sub>p</sub> of matching form. If it overlaps y<sub>h</sub>, multiply by x<sup>s</sup>, where s is the root multiplicity. Fast choice for standard forcing."),
    ("Variation of parameters", "For <b>y''+p y'+q y=g</b> with known y<sub>1</sub>,y<sub>2</sub>, W=y<sub>1</sub>y'<sub>2</sub>-y'<sub>1</sub>y<sub>2</sub>.", "<b>y<sub>p</sub>=-y<sub>1</sub>∫y<sub>2</sub>g/W dx + y<sub>2</sub>∫y<sub>1</sub>g/W dx</b>. Works for variable coefficients and arbitrary forcing."),
    ("Euler-Cauchy", "<b>ax²y''+bxy'+cy=g(x)</b>. Try y=x<sup>m</sup> in homogeneous equation; equivalently t=ln x.", "Use for scale-invariant models. Repeated/complex m follow the same characteristic-root pattern with ln x."),
    ("Mass-spring-damper", "<b>m y''+c y'+ky=F(t)</b>. Natural frequency ω<sub>0</sub>=√(k/m); damping ratio ζ=c/(2√mk).", "Models vibration. ζ&lt;1 underdamped, =1 critical, &gt;1 overdamped. Sinusoidal forcing near ω<sub>0</sub> produces resonance when damping is small."),
    ("RLC circuit", "<b>Lq''+Rq'+q/C=E(t)</b>; current i=q'.", "Same mathematical family as the oscillator; use for transient and forced circuit response."),
])

story += section("4. Systems and qualitative dynamics", [
    ("Linear system", "<b>x' = A x + f(t)</b>. Homogeneous solution <b>x(t)=e<sup>At</sup>x<sub>0</sub></b>.", "For constant A, use eigenpairs: x=Σc<sub>i</sub>e<sup>λ<sub>i</sub>t</sup>v<sub>i</sub>. Models coupled compartments, circuits, mechanics, and linearized dynamics."),
    ("Forced linear system", "x'=Ax+f(t).", "Variation of constants: <b>x=e<sup>At</sup>x<sub>0</sub>+∫<sub>0</sub><sup>t</sup>e<sup>A(t-s)</sup>f(s)ds</b>. Use for inputs acting on coupled systems."),
    ("Nonlinear autonomous system", "<b>x'=f(x,y), y'=g(x,y)</b>. Critical points satisfy f=g=0; linearize with Jacobian J.", "Eigenvalues of J classify locally: both Re λ&lt;0 stable; both &gt;0 unstable; opposite signs saddle; complex pair spiral. Use phase plane when closed forms are unavailable."),
])

story.append(PageBreak())
story += section("5. Series, special functions, and eigenvalue problems", [
    ("Ordinary point power series", "For y''+p(x)y'+q(x)y=0 with p,q analytic at x<sub>0</sub>, set <b>y=Σa<sub>n</sub>(x-x<sub>0</sub>)<sup>n</sup></b>.", "Substitute and equate powers to get a recurrence. Use near an ordinary point when elementary solutions are unavailable."),
    ("Regular singular point (Frobenius)", "If (x-x<sub>0</sub>)p and (x-x<sub>0</sub>)²q are analytic, try <b>y=Σa<sub>n</sub>(x-x<sub>0</sub>)<sup>n+r</sup></b>.", "Indicial equation determines r. Use for Bessel, Legendre, and other singular-coefficient equations."),
    ("Legendre equation", "<b>(1-x²)y''-2xy'+n(n+1)y=0</b>; regular solutions P<sub>n</sub>(x).", "Use on -1≤x≤1, especially spherical/angular boundary problems. Orthogonality: ∫<sub>-1</sub><sup>1</sup>P<sub>m</sub>P<sub>n</sub>dx=2δ<sub>mn</sub>/(2n+1)."),
    ("Bessel equation", "<b>x²y''+xy'+(x²-ν²)y=0</b>; solutions J<sub>ν</sub>,Y<sub>ν</sub>.", "Use for radial cylindrical geometry: membranes, pipes, heat/conduction in cylinders. Require regularity at x=0 usually selects J<sub>ν</sub>."),
    ("Sturm-Liouville", "<b>(p y')'+(λw-q)y=0</b> with homogeneous boundary conditions.", "Eigenfunctions for distinct λ are weight-orthogonal: ∫w y<sub>m</sub>y<sub>n</sub>dx=0. Use to expand initial/boundary data in PDE separation of variables."),
])

story += section("6. Integral transforms and convolution", [
    ("Laplace transform", "<b>L{f}=F(s)=∫<sub>0</sub><sup>∞</sup>e<sup>-st</sup>f(t)dt</b>. Key: L{f'}=sF-f(0), L{f''}=s²F-sf(0)-f'(0).", "Best for IVPs with initial data, discontinuities, impulses, and piecewise forcing. Transform ODE → algebra in s, then invert."),
    ("Shift rules", "L{e<sup>at</sup>f}=F(s-a). L{u(t-a)f(t-a)}=e<sup>-as</sup>F(s).", "Use exponential shifts for growth/decay and Heaviside shifts for switched-on inputs."),
    ("Impulse", "<b>L{δ(t-a)}=e<sup>-as</sup></b>. For m y''+...=Jδ(t-a), integrate across a to get m[y']<sub>a-</sub><sup>a+</sup>=J.", "Models a sudden kick, impact, or idealized short pulse."),
    ("Convolution", "<b>(f*g)(t)=∫<sub>0</sub><sup>t</sup>f(τ)g(t-τ)dτ</b>; <b>L{f*g}=FG</b>.", "Use when inverse transforms are products or to express a linear system’s response to an input."),
    ("Fourier series", "On (-L,L): <b>f~a<sub>0</sub>/2+Σ[a<sub>n</sub>cos(nπx/L)+b<sub>n</sub>sin(nπx/L)]</b>. a<sub>n</sub>=1/L∫f cos; b<sub>n</sub>=1/L∫f sin.", "Use periodic data and separated PDE solutions. Even data gives cosine-only; odd data gives sine-only."),
    ("Fourier transform", "Convention: <b>F(ω)=∫<sub>-∞</sub><sup>∞</sup>f(x)e<sup>-iωx</sup>dx</b>; f=(1/2π)∫F e<sup>iωx</sup>dω.", "Use nonperiodic whole-line heat/wave/linear systems; derivatives become multiplication: F{f'}=iωF."),
])

story.append(PageBreak())
story += section("7. PDE families: relation, behavior, and standard solution", [
    ("Classification (2 variables)", "<b>Au<sub>xx</sub>+2Bu<sub>xy</sub>+Cu<sub>yy</sub>+...=0</b>. D=B²-AC: D&lt;0 elliptic; D=0 parabolic; D&gt;0 hyperbolic.", "Elliptic: spatial equilibrium; parabolic: smoothing/diffusion in time; hyperbolic: finite-speed waves/signals. Classification guides suitable data and coordinates."),
    ("Laplace / Poisson (elliptic)", "<b>∇²u=0</b> (Laplace); <b>∇²u=f</b> (Poisson).", "Steady temperature, electrostatic/gravitational potential, incompressible potential flow. Specify boundary values (Dirichlet) or normal derivative (Neumann, compatibility required)."),
    ("Heat / diffusion (parabolic)", "<b>u<sub>t</sub>=κ∇²u</b>, κ&gt;0. In 1D 0&lt;x&lt;L with u(0,t)=u(L,t)=0: <b>u=Σb<sub>n</sub>sin(nπx/L)e<sup>-κ(nπ/L)²t</sup></b>.", "Temperature, diffusion, concentration. Initial condition evolves and high-frequency variations decay fastest."),
    ("Wave (hyperbolic)", "<b>u<sub>tt</sub>=c²u<sub>xx</sub></b>. On whole line: <b>u(x,t)=[f(x-ct)+f(x+ct)]/2+[1/(2c)]∫<sub>x-ct</sub><sup>x+ct</sup>g(s)ds</b>.", "Vibrating strings, sound, signals. D'Alembert formula uses initial displacement f and velocity g; information travels along characteristics x±ct=constant."),
    ("Separation of variables", "Try <b>u(x,t)=X(x)T(t)</b>. Spatial boundary conditions create an eigenvalue problem for X; fit initial data with Fourier/eigenfunction coefficients.", "Primary method on rectangles, finite strings/rods, membranes, and other separable domains."),
    ("2D membrane / rectangle", "For u<sub>tt</sub>=c²(u<sub>xx</sub>+u<sub>yy</sub>) with fixed rectangle: modes sin(mπx/a)sin(nπy/b), ω<sub>mn</sub>=cπ√[(m/a)²+(n/b)²].", "Use for drumheads/membranes and 2D vibration; initial shape and velocity determine modal amplitudes."),
    ("Polar/cylindrical radial PDE", "In polar, <b>∇²u=u<sub>rr</sub>+(1/r)u<sub>r</sub>+(1/r²)u<sub>θθ</sub></b>. Radial eigenfunctions are Bessel functions.", "Use circular membranes, cylinders, and radially symmetric heat/potential problems."),
])

story += section("8. Numerical methods: when an analytic form is not the point", [
    ("Euler (first order)", "For y'=f(x,y): <b>y<sub>n+1</sub>=y<sub>n</sub>+h f(x<sub>n</sub>,y<sub>n</sub>)</b>.", "Simple IVP approximation and conceptual baseline. First-order global error; reduce h cautiously."),
    ("Improved Euler / RK2", "Predict y*=y<sub>n</sub>+hf(x<sub>n</sub>,y<sub>n</sub>); correct <b>y<sub>n+1</sub>=y<sub>n</sub>+h[f<sub>n</sub>+f(x<sub>n+1</sub>,y*)]/2</b>.", "More accurate than Euler for smooth IVPs at modest cost."),
    ("Runge-Kutta 4", "k<sub>1</sub>=f(x,y); k<sub>2</sub>=f(x+h/2,y+hk<sub>1</sub>/2); k<sub>3</sub>=f(x+h/2,y+hk<sub>2</sub>/2); k<sub>4</sub>=f(x+h,y+hk<sub>3</sub>). <b>y<sub>n+1</sub>=y<sub>n</sub>+h(k<sub>1</sub>+2k<sub>2</sub>+2k<sub>3</sub>+k<sub>4</sub>)/6</b>.", "Standard accurate general-purpose solver for nonstiff smooth IVPs (global O(h⁴))."),
    ("Finite differences", "u''(x<sub>i</sub>)≈(u<sub>i+1</sub>-2u<sub>i</sub>+u<sub>i-1</sub>)/h². Heat explicit: <b>u<sub>i</sub><sup>n+1</sup>=u<sub>i</sub><sup>n</sup>+r(u<sub>i+1</sub><sup>n</sup>-2u<sub>i</sub><sup>n</sup>+u<sub>i-1</sub><sup>n</sup>)</b>, r=κΔt/Δx².", "Use BVPs/PDE grids. Explicit 1D heat scheme needs r≤1/2 for stability; implicit methods cost a linear solve but are more stable."),
])

story += [Spacer(1, 4), Paragraph("Workflow: identify order and linearity → inspect the equation’s relation/form → apply the matching substitution or transform → impose the given initial/boundary data → check domain, units, and qualitative behavior. This is a study aid, not a replacement for derivations or problem-specific assumptions.", styles["Foot"])]

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=.55*inch, rightMargin=.55*inch, topMargin=.45*inch, bottomMargin=.6*inch)
doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
print(OUT)
