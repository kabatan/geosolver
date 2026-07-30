use std::sync::Mutex;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyModule};

const SEMANTIC_ABI: &str = "geotarget.native-flat-kernel/ieee754-bf53-v1";

const SCALAR: u8 = 0;
const POINT: u8 = 1;
const LINE: u8 = 2;
const CIRCLE: u8 = 3;

const EXACT_INT: u8 = 1;
const BF53_LITERAL: u8 = 2;
const BF53_INPUT: u8 = 3;
const ADD: u8 = 5;
const SUB: u8 = 6;
const MUL: u8 = 7;
const DIV: u8 = 8;
const NEG: u8 = 10;
const POS: u8 = 11;
const SQRT: u8 = 12;
const ABS: u8 = 15;
const MAKE_POINT: u8 = 20;
const POINT_X: u8 = 21;
const POINT_Y: u8 = 22;
const MIDPOINT: u8 = 23;
const POINT_ON_SEGMENT: u8 = 24;
const MAKE_CIRCLE: u8 = 30;
const CIRCLE_CENTER: u8 = 31;
const CIRCLE_RADIUS: u8 = 32;
const LINE_PP: u8 = 40;
const LINE_ABC: u8 = 41;
const DISTANCE_PP: u8 = 50;
const DISTANCE_PL: u8 = 51;
const DISTANCE_LP: u8 = 52;
const DISTANCE_PC: u8 = 53;
const DISTANCE_CP: u8 = 54;
const AREA: u8 = 55;

type RawRef = (u8, usize);
type RawInstruction = (u8, u8, usize, Vec<RawRef>, Option<f64>, Option<i64>);
type RawConstraint = (Vec<RawInstruction>, RawRef, RawRef);

#[derive(Clone, Copy)]
struct SlotRef {
    kind: u8,
    index: usize,
}

#[derive(Clone)]
struct Instruction {
    op: u8,
    output: SlotRef,
    operands: Vec<SlotRef>,
    float_payload: Option<f64>,
    int_payload: Option<i64>,
}

struct ConstraintTape {
    instructions: Vec<Instruction>,
    left: SlotRef,
    right: SlotRef,
}

struct Buffers {
    scalars: Vec<f64>,
    point_x: Vec<f64>,
    point_y: Vec<f64>,
    line_a: Vec<f64>,
    line_b: Vec<f64>,
    line_c: Vec<f64>,
    circle_x: Vec<f64>,
    circle_y: Vec<f64>,
    circle_r: Vec<f64>,
}

impl Buffers {
    fn new(counts: (usize, usize, usize, usize)) -> Self {
        let (scalars, points, lines, circles) = counts;
        Self {
            scalars: vec![0.0; scalars],
            point_x: vec![0.0; points],
            point_y: vec![0.0; points],
            line_a: vec![0.0; lines],
            line_b: vec![0.0; lines],
            line_c: vec![0.0; lines],
            circle_x: vec![0.0; circles],
            circle_y: vec![0.0; circles],
            circle_r: vec![0.0; circles],
        }
    }
}

fn slot(raw: RawRef) -> SlotRef {
    SlotRef {
        kind: raw.0,
        index: raw.1,
    }
}

fn instruction(raw: RawInstruction) -> Instruction {
    Instruction {
        op: raw.0,
        output: SlotRef {
            kind: raw.1,
            index: raw.2,
        },
        operands: raw.3.into_iter().map(slot).collect(),
        float_payload: raw.4,
        int_payload: raw.5,
    }
}

fn certified(value: f64) -> bool {
    value.is_finite() && !value.is_subnormal() && !(value == 0.0 && value.is_sign_negative())
}

fn scalar(buffers: &Buffers, reference: SlotRef) -> Option<f64> {
    (reference.kind == SCALAR)
        .then(|| buffers.scalars.get(reference.index).copied())
        .flatten()
}

fn point(buffers: &Buffers, reference: SlotRef) -> Option<(f64, f64)> {
    if reference.kind != POINT {
        return None;
    }
    Some((
        *buffers.point_x.get(reference.index)?,
        *buffers.point_y.get(reference.index)?,
    ))
}

fn line(buffers: &Buffers, reference: SlotRef) -> Option<(f64, f64, f64)> {
    if reference.kind != LINE {
        return None;
    }
    Some((
        *buffers.line_a.get(reference.index)?,
        *buffers.line_b.get(reference.index)?,
        *buffers.line_c.get(reference.index)?,
    ))
}

fn circle(buffers: &Buffers, reference: SlotRef) -> Option<(f64, f64, f64)> {
    if reference.kind != CIRCLE {
        return None;
    }
    Some((
        *buffers.circle_x.get(reference.index)?,
        *buffers.circle_y.get(reference.index)?,
        *buffers.circle_r.get(reference.index)?,
    ))
}

fn checked(value: f64) -> Option<f64> {
    certified(value).then_some(value)
}

fn execute(instructions: &[Instruction], inputs: &[f64], buffers: &mut Buffers) -> Option<()> {
    for item in instructions {
        let args = &item.operands;
        match item.op {
            EXACT_INT => {
                let value = item.int_payload? as f64;
                buffers.scalars[item.output.index] = checked(value)?;
            }
            BF53_LITERAL => {
                buffers.scalars[item.output.index] = checked(item.float_payload?)?;
            }
            BF53_INPUT => {
                let index = usize::try_from(item.int_payload?).ok()?;
                buffers.scalars[item.output.index] = *inputs.get(index)?;
            }
            ADD | SUB | MUL | DIV => {
                let left = scalar(buffers, *args.first()?)?;
                let right = scalar(buffers, *args.get(1)?)?;
                let result = match item.op {
                    ADD => left + right,
                    SUB => left - right,
                    MUL => left * right,
                    DIV if right != 0.0 => left / right,
                    _ => return None,
                };
                buffers.scalars[item.output.index] = checked(result)?;
            }
            NEG | POS | ABS | SQRT => {
                let value = scalar(buffers, *args.first()?)?;
                let result = match item.op {
                    NEG => -value,
                    POS => value,
                    ABS => value.abs(),
                    SQRT if value >= 0.0 => value.sqrt(),
                    _ => return None,
                };
                buffers.scalars[item.output.index] = checked(result)?;
            }
            MAKE_POINT => {
                let x = scalar(buffers, *args.first()?)?;
                let y = scalar(buffers, *args.get(1)?)?;
                buffers.point_x[item.output.index] = x;
                buffers.point_y[item.output.index] = y;
            }
            POINT_X | POINT_Y => {
                let (x, y) = point(buffers, *args.first()?)?;
                buffers.scalars[item.output.index] = if item.op == POINT_X { x } else { y };
            }
            MIDPOINT | POINT_ON_SEGMENT => {
                let (ax, ay) = point(buffers, *args.first()?)?;
                let (bx, by) = point(buffers, *args.get(1)?)?;
                let (x, y) = if item.op == MIDPOINT {
                    (
                        checked(checked(ax + bx)? / 2.0)?,
                        checked(checked(ay + by)? / 2.0)?,
                    )
                } else {
                    let t = scalar(buffers, *args.get(2)?)?;
                    let dx = checked(bx - ax)?;
                    let dy = checked(by - ay)?;
                    (
                        checked(ax + checked(t * dx)?)?,
                        checked(ay + checked(t * dy)?)?,
                    )
                };
                buffers.point_x[item.output.index] = x;
                buffers.point_y[item.output.index] = y;
            }
            MAKE_CIRCLE => {
                let (x, y) = point(buffers, *args.first()?)?;
                let radius = scalar(buffers, *args.get(1)?)?;
                if radius < 0.0 {
                    return None;
                }
                buffers.circle_x[item.output.index] = x;
                buffers.circle_y[item.output.index] = y;
                buffers.circle_r[item.output.index] = radius;
            }
            CIRCLE_CENTER => {
                let (x, y, _) = circle(buffers, *args.first()?)?;
                buffers.point_x[item.output.index] = x;
                buffers.point_y[item.output.index] = y;
            }
            CIRCLE_RADIUS => {
                let (_, _, radius) = circle(buffers, *args.first()?)?;
                buffers.scalars[item.output.index] = radius;
            }
            LINE_PP => {
                let (ax, ay) = point(buffers, *args.first()?)?;
                let (bx, by) = point(buffers, *args.get(1)?)?;
                let a = checked(ay - by)?;
                let b = checked(bx - ax)?;
                let c = checked(checked(ax * by)? - checked(bx * ay)?)?;
                let norm = checked(checked(checked(a * a)? + checked(b * b)?)?.sqrt())?;
                if norm == 0.0 {
                    return None;
                }
                buffers.line_a[item.output.index] = checked(a / norm)?;
                buffers.line_b[item.output.index] = checked(b / norm)?;
                buffers.line_c[item.output.index] = checked(c / norm)?;
            }
            LINE_ABC => {
                let a = scalar(buffers, *args.first()?)?;
                let b = scalar(buffers, *args.get(1)?)?;
                let c = scalar(buffers, *args.get(2)?)?;
                let norm = checked(checked(checked(a * a)? + checked(b * b)?)?.sqrt())?;
                if norm == 0.0 {
                    return None;
                }
                buffers.line_a[item.output.index] = checked(a / norm)?;
                buffers.line_b[item.output.index] = checked(b / norm)?;
                buffers.line_c[item.output.index] = checked(c / norm)?;
            }
            DISTANCE_PP => {
                let (ax, ay) = point(buffers, *args.first()?)?;
                let (bx, by) = point(buffers, *args.get(1)?)?;
                let dx = checked(ax - bx)?;
                let dy = checked(ay - by)?;
                let squared = checked(checked(dx * dx)? + checked(dy * dy)?)?;
                buffers.scalars[item.output.index] = checked(squared.sqrt())?;
            }
            DISTANCE_PL | DISTANCE_LP => {
                let (point_ref, line_ref) = if item.op == DISTANCE_PL {
                    (*args.first()?, *args.get(1)?)
                } else {
                    (*args.get(1)?, *args.first()?)
                };
                let (x, y) = point(buffers, point_ref)?;
                let (a, b, c) = line(buffers, line_ref)?;
                let value = checked(checked(checked(a * x)? + checked(b * y)?)? + c)?;
                buffers.scalars[item.output.index] = checked(value.abs())?;
            }
            DISTANCE_PC | DISTANCE_CP => {
                let (point_ref, circle_ref) = if item.op == DISTANCE_PC {
                    (*args.first()?, *args.get(1)?)
                } else {
                    (*args.get(1)?, *args.first()?)
                };
                let (x, y) = point(buffers, point_ref)?;
                let (cx, cy, radius) = circle(buffers, circle_ref)?;
                let dx = checked(x - cx)?;
                let dy = checked(y - cy)?;
                let squared = checked(checked(dx * dx)? + checked(dy * dy)?)?;
                let distance = checked(squared.sqrt())?;
                buffers.scalars[item.output.index] = checked(checked(distance - radius)?.abs())?;
            }
            AREA => {
                if args.len() < 3 {
                    return None;
                }
                let mut total = 0.0;
                for index in 0..args.len() {
                    let (ax, ay) = point(buffers, args[index])?;
                    let (bx, by) = point(buffers, args[(index + 1) % args.len()])?;
                    let cross = checked(checked(ax * by)? - checked(ay * bx)?)?;
                    total = checked(total + cross)?;
                }
                buffers.scalars[item.output.index] = checked(total.abs() / 2.0)?;
            }
            _ => return None,
        }
    }
    Some(())
}

#[pyclass]
struct NativeProgram {
    variable_count: usize,
    construction: Vec<Instruction>,
    constraints: Vec<ConstraintTape>,
    buffers: Mutex<Buffers>,
}

#[pymethods]
impl NativeProgram {
    #[new]
    fn new(
        variable_count: usize,
        slot_counts: (usize, usize, usize, usize),
        construction: &Bound<'_, PyAny>,
        constraints: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        let raw_construction = construction.extract::<Vec<RawInstruction>>()?;
        let raw_constraints = constraints.extract::<Vec<RawConstraint>>()?;
        let construction = raw_construction.into_iter().map(instruction).collect();
        let constraints = raw_constraints
            .into_iter()
            .map(|raw| ConstraintTape {
                instructions: raw.0.into_iter().map(instruction).collect(),
                left: slot(raw.1),
                right: slot(raw.2),
            })
            .collect();
        Ok(Self {
            variable_count,
            construction,
            constraints,
            buffers: Mutex::new(Buffers::new(slot_counts)),
        })
    }

    fn evaluate(&self, values: Vec<f64>) -> PyResult<Option<Vec<f64>>> {
        if values.len() != self.variable_count {
            return Err(PyValueError::new_err("native kernel dimension mismatch"));
        }
        if values.iter().any(|value| !certified(*value)) {
            return Ok(None);
        }
        let mut buffers = self
            .buffers
            .lock()
            .map_err(|_| PyValueError::new_err("native kernel buffer lock poisoned"))?;
        if execute(&self.construction, &values, &mut buffers).is_none() {
            return Ok(None);
        }
        let mut residuals = Vec::with_capacity(self.constraints.len());
        for constraint in &self.constraints {
            if execute(&constraint.instructions, &values, &mut buffers).is_none() {
                return Ok(None);
            }
            let left = scalar(&buffers, constraint.left).ok_or_else(|| {
                PyValueError::new_err("native constraint left root is not scalar")
            })?;
            let right = scalar(&buffers, constraint.right).ok_or_else(|| {
                PyValueError::new_err("native constraint right root is not scalar")
            })?;
            residuals.push(match checked(left - right) {
                Some(value) => value,
                None => return Ok(None),
            });
        }
        Ok(Some(residuals))
    }
}

#[pyfunction]
fn semantic_abi() -> &'static str {
    SEMANTIC_ABI
}

#[pymodule]
fn _native_kernel(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeProgram>()?;
    module.add_function(wrap_pyfunction!(semantic_abi, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::certified;

    #[test]
    fn value_class_gate_rejects_unsafe_boundaries() {
        assert!(certified(1.0));
        assert!(certified(0.0));
        assert!(!certified(-0.0));
        assert!(!certified(f64::from_bits(1)));
        assert!(!certified(f64::INFINITY));
        assert!(!certified(f64::NAN));
    }
}
