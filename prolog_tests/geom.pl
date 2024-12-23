:- use_module(library(clpr)).

point(_, _).

x_coord(point(X, _), X).
y_coord(point(_, Y), Y).

dx(point(X0, _), point(X1, _), DX) :- DX = X1 - X0.
dy(point(_, Y0), point(_, Y1), DY) :- DY = Y1 - Y0.

a_to_b(point(X0, Y0), point(X1, Y1), point(X1 - X0, Y1 - Y0)).

pdist(P0, P1, Dist) :- dx(P0, P1, DX), dy(P0, P1, DY), {Dist * Dist = DX * DX + DY * DY}.
plength(point(X, Y), Length) :- {Length * Length = X * X + Y * Y}.
rcw90deg(point(X0, Y0), point(X, Y)) :- {
    CosT = 0,
    SinT = 1,

    X0 * CosT - Y0 * SinT - X = 0,
    X0 * SinT + Y0 * CosT - Y = 0
}.
rccw90deg(point(X0, Y0), point(X, Y)) :- {
    CosT = 0,
    SinT = -1,

    -X0 * CosT + Y0 * SinT - X = 0,
    -X0 * SinT - Y0 * CosT - Y = 0
}.

ang_norm(AngleValue, Result) :- (AngleValue >= 0, Result = AngleValue); (AngleValue < 0, Result = 2 * pi + AngleValue).

% angle is relative to PC
pangle(P, PC, Angle) :- dx(PC, P, DX), dy(PC, P, DY), {tan(Angle) =:= DY/DX}.

incident(point(X0, Y0), point(X1, Y1)) :-
    {X0 - X1 = 0},
    {Y0 - Y1 = 0}.

% Line Segment
line_segment(point(_X0, _Y0), point(_X1, _Y1)).

% Circle Arc
circle_arc(point(X0, Y0), point(X1, Y1), point(XC, YC)) :-
    {(XC - X0) * (XC - X0) + (YC - Y0) * (YC - Y0)- 
    (XC - X1) * (XC - X1) - (YC - Y1) * (YC - Y1) = 0}.

p0(line_segment(P0, _), P0).
p0(circle_arc(P0, _, _), P0).

p1(line_segment(_, P1), P1).
p1(circle_arc(_, P1, _), P1).

pn(line_segment(P0, _), end(p0), P0).
pn(line_segment(_, P1), end(p1), P1).
pn(circle_arc(P0, _, _), end(p0), P0).
pn(circle_arc(_, P1, _), end(p1), P1).

pc(circle_arc(_, _, PC), PC).
radius(circle_arc(P1, _, PC), R) :- pdist(PC, P1, R).

angle_p0(circle_arc(P0, _, PC), A) :- pangle(P0, PC, A).
angle_p1(circle_arc(_, P1, PC), A) :- pangle(P1, PC, A).

cw_sum(point(X0, Y0), point(X1, Y1), Sum) :-
    {Sum =:= (X1 - X0) * (Y1 + Y0)}.

clockwise(circle_arc(P1, P2, P3)) :-
    cw_sum(P3, P1, S1),
    cw_sum(P1, P2, S2),
    cw_sum(P2, P3, S3),
    (S1 + S2 + S3) >= 0.

closed(Curve) :- p1(Curve, C1), p2(Curve, C2), incident(C1, C2).
not_closed(Curve) :- \+closed(Curve).

curves_connected(C0, EndC0, C1, EndC1) :-
    pn(C0, EndC0, P0),
    pn(C1, EndC1, P1),
    incident(P0, P1).

sweep_angle(CircleArc, Angle) :- angle_p1(CircleArc, A1), angle_p0(CircleArc, A0), Angle = A1 - A0.

% normalize a vector
normalized(Point, Result) :-
    plength(Point, Length),
    x_coord(Point, DX),
    y_coord(Point, DY),
    x_coord(Result, RDX),
    y_coord(Result, RDY),
    {RDX =:= DX / Length},
    {RDY =:= DY / Length}.

on_curve_line_segment(
    line_segment(point(X0, Y0), point(X1, Y1)),
    point(PX, PY)) :-
    {X_MIN = min(X0, X1), X_MAX = max(X0, X1)},
    {PX >= X_MIN, PX =< X_MAX},
    a_to_b(point(X0, Y0), point(PX, PY), PointVec),
    normalized(PointVec, PointVecNorm),
    a_to_b(point(X0, Y0), point(X1, Y1), LineVec),
    normalized(LineVec, LineVecNorm),
    incident(LineVecNorm, PointVecNorm).

on_curve_circle_arc(CircleArc, Point) :-
    radius(CircleArc, R),
    pc(CircleArc, PC),
    pdist(PC, Point, DR),
    {R =:= DR},
    angle_p0(CircleArc, AP0),
    angle_p1(CircleArc, AP1),
    pangle(Point, PC, Angle),
    ((clockwise(CircleArc), Angle =< AP0, Angle >= AP1) ; (\+ clockwise(CircleArc), Angle >= AP0, Angle =< AP1)).

% 2d rotation matrix:
% cos -sin
% sin cos

% for 90 degrees, cos(theta) = 0 sin(theta) = 1
% rx = 0x  -1y
% ry = 1x   0y
% rx = -y
% ry = x

tangent_to_circle_arc(CircleArc, Point, Tangent) :-
    on_curve_circle_arc(CircleArc, Point),
    pc(CircleArc, PC),
    dx(PC, Point, PDX),
    dy(PC, Point, PDY),
    (
        (clockwise(CircleArc),
            x_coord(Tangent, PDY),
            y_coord(Tangent, -PDX));
        (\+ clockwise(CircleArc),
            x_coord(Tangent, -PDY),
            y_coord(Tangent, PDX))
    ).

tangent_to_line_segment(LineSegment, Point, Tangent) :-
    on_curve_line_segment(LineSegment, Point),
    p0(LineSegment, P0),
    p1(LineSegment, P1),
    a_to_b(P0, P1, LineVec),
    normalized(LineVec, Tangent).

tangent(LineSegment, end(L), CircleArc, end(C)) :-
    pn(LineSegment, end(L), PL),
    pn(CircleArc, end(C), PC),
    tangent_to_line_segment(LineSegment, PL, Tangent),
    tangent_to_circle_arc(CircleArc, PC, Tangent).

write_circle_arc(CircleArc) :-
    p0(CircleArc, P0),
    p1(CircleArc, P1),
    pc(CircleArc, C),
    radius(CircleArc, R_exp),
    R is R_exp,
    sweep_angle(CircleArc, Angle_exp),
    Angle is 360 * (0.5 * Angle_exp / pi),
    ((clockwise(CircleArc), CW="CW"); CW="CCW"),
    write("Circle Arc "),
    write_point(C),
    write(" "),
    write_point(P0),
    write(" -> "),
    write_point(P1),
    write(" "),
    write(CW),
    write(" R="),
    write(R),
    write(" Sweep Angle="),
    write(Angle),
    write("deg").

write_point(Point) :-
    point(Point),
    x_coord(Point, X),
    y_coord(Point, Y),
    {XVal =:= X},
    {YVal =:= Y},
    write("("),
    write(XVal),
    write(", "),
    write(YVal),
    write(")").








% ================================================
%
%                  Graphics
%
% ================================================
:- use_module(library(pce)).

gradians(ValueDeg, ValueRad) :- ValueRad is (2 * pi * ValueDeg / 360).
gdegrees(ValueRad, ValueDeg) :- ValueDeg is 180 * ValueRad / pi.

graph_point(Point, Pic) :-
    x_coord(Point, CCX),
    y_coord(Point, CCY),
    CX is CCX,
    CY is CCY,
    send(Pic, display,
        new(_, circle(5)), point(CX - 1.5, CY - 1.5)).

graph_circle_arc(CircleArc, Pic) :-
    radius(CircleArc, RExp),
    R is RExp,
    pc(CircleArc, C),
    x_coord(C, CX),
    y_coord(C, CY),
    p0(CircleArc, P0),
    p1(CircleArc, P1),
    graph_point(P0, Pic),
    graph_point(P1, Pic),
    angle_p0(CircleArc, StartAngleRad),
    sweep_angle(CircleArc, SweepAngleRad),
    gdegrees(StartAngleRad, StartAngleDeg),
    gdegrees(SweepAngleRad, SweepAngleDeg),
    (
        (clockwise(CircleArc), SweepAngleOrient is -SweepAngleDeg) ;
        (SweepAngleOrient is SweepAngleDeg)
    ),
    send(Pic, display,
        new(A, arc(R, StartAngleDeg, SweepAngleOrient))),
        send(A, position, point(CX, CY)),
        send(A, close, none).

graph_line_segment(line_segment(P0, P1), Pic) :-
    graph_point(P0, Pic),
    graph_point(P1, Pic),
    x_coord(P0, P0X),
    y_coord(P0, P0Y),
    x_coord(P1, P1X),
    y_coord(P1, P1Y),
    send(Pic, display,
        new(line(P0X, P0Y, P1X, P1Y))).


point_values_concrete(point(XIn, YIn), point(XOut, YOut)) :-
    XOut is XIn,
    YOut is YIn.


test :-
    X = circle_arc(point(XX, 100), point(100, 150), point(100, 100)),
    LS = line_segment(point(10, 20), point(XX, 100)),
    curves_connected(X, end(p0), LS, end(p1)),
    XXX is XX,
    write(XX).
    %    tangent(LS, end(p1), X, end(p0)).

%    write("Solver success"),
%    new(Pic, picture('Display')),
%    graph_circle_arc(X, Pic),
%    graph_line_segment(LS, Pic),
%    send(Pic, open).

