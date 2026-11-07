use std::cmp::Ordering;
use std::fmt;
use std::str::FromStr;

use bigdecimal::num_bigint::BigInt;
use bigdecimal::{BigDecimal, One, RoundingMode, Signed, Zero};

const PRECISION: u64 = 28;
const POWER_PRECISION: u64 = PRECISION * 2;
const MAX_EXPONENT: i64 = 9_999;
const MAX_TEXT_LEN: usize = 4_096;

#[derive(Clone, Debug)]
pub struct Decimal(BigDecimal);

fn scale_of(value: &BigDecimal) -> i64 {
    value.fractional_digit_count()
}

fn adjusted_of(value: &BigDecimal) -> i64 {
    value.digits() as i64 - 1 - scale_of(value)
}

fn mantissa_at(value: &BigDecimal, scale: i64) -> BigInt {
    value.with_scale(scale).into_bigint_and_scale().0
}

fn product(left: &BigDecimal, right: &BigDecimal) -> BigDecimal {
    let (a, a_scale) = left.as_bigint_and_scale();
    let (b, b_scale) = right.as_bigint_and_scale();
    BigDecimal::new(a.as_ref() * b.as_ref(), a_scale + b_scale)
}

fn rounded(mut value: BigDecimal, precision: u64) -> BigDecimal {
    while value.digits() > precision {
        let scale = scale_of(&value) - (value.digits() - precision) as i64;
        value = value.with_scale_round(scale, RoundingMode::HalfEven);
    }
    value
}

fn finish(value: BigDecimal) -> Option<Decimal> {
    let value = rounded(value, PRECISION);
    (scale_of(&value).abs() <= MAX_EXPONENT && adjusted_of(&value).abs() <= MAX_EXPONENT)
        .then_some(Decimal(value))
}

fn quotient(left: &BigDecimal, right: &BigDecimal, precision: u64) -> BigDecimal {
    let (a, b) = (
        left.as_bigint_and_scale().0.abs(),
        right.as_bigint_and_scale().0.abs(),
    );
    let shift = right.digits() as i64 - left.digits() as i64 + precision as i64 + 1;
    let ten = BigInt::from(10u8);
    let (numerator, denominator) = if shift > 0 {
        (a * ten.pow(shift as u32), b)
    } else {
        (a, b * ten.pow(shift.unsigned_abs() as u32))
    };
    let mut digits = &numerator / &denominator;
    let exact = (&numerator % &denominator).is_zero();
    let ideal_scale = scale_of(left) - scale_of(right);
    let mut scale = ideal_scale + shift;
    if exact {
        while scale > ideal_scale && (&digits % &ten).is_zero() {
            digits /= &ten;
            scale -= 1;
        }
    } else if (&digits % 5u8).is_zero() {
        // An inexact quotient must not end in 0 or 5, or half-even rounding would see a false tie.
        digits += 1u8;
    }
    BigDecimal::new(digits, scale)
}

fn power(base: &BigDecimal, exponent: i64) -> Option<BigDecimal> {
    let bits = exponent.unsigned_abs();
    let base = if exponent < 0 {
        rounded(
            quotient(&BigDecimal::one(), base, POWER_PRECISION),
            POWER_PRECISION,
        )
    } else {
        base.clone()
    };
    let mut result = base.clone();
    for bit in (0..bits.ilog2()).rev() {
        result = rounded(product(&result, &result), POWER_PRECISION);
        if bits >> bit & 1 == 1 {
            result = rounded(product(&result, &base), POWER_PRECISION);
        }
        if adjusted_of(&result).abs() > MAX_EXPONENT {
            return None;
        }
    }
    Some(result)
}

fn is_plain_number(text: &str) -> bool {
    let unsigned = text.strip_prefix('-').unwrap_or(text);
    let (whole, fraction) = unsigned.split_once('.').unwrap_or((unsigned, "0"));
    !whole.is_empty()
        && !fraction.is_empty()
        && whole.bytes().all(|byte| byte.is_ascii_digit())
        && fraction.bytes().all(|byte| byte.is_ascii_digit())
}

impl Decimal {
    pub fn parse(text: &str) -> Option<Self> {
        if text.len() > MAX_TEXT_LEN || !is_plain_number(text) {
            return None;
        }
        BigDecimal::from_str(text).ok().map(Self)
    }

    pub fn is_zero(&self) -> bool {
        self.0.is_zero()
    }

    pub fn add(&self, other: &Self) -> Option<Self> {
        let scale = scale_of(&self.0).max(scale_of(&other.0));
        let sum = mantissa_at(&self.0, scale) + mantissa_at(&other.0, scale);
        finish(BigDecimal::new(sum, scale))
    }

    pub fn sub(&self, other: &Self) -> Option<Self> {
        let scale = scale_of(&self.0).max(scale_of(&other.0));
        let difference = mantissa_at(&self.0, scale) - mantissa_at(&other.0, scale);
        finish(BigDecimal::new(difference, scale))
    }

    pub fn mul(&self, other: &Self) -> Option<Self> {
        finish(product(&self.0, &other.0))
    }

    pub fn div(&self, other: &Self) -> Option<Self> {
        if other.0.is_zero() {
            return None;
        }
        let result = quotient(&self.0, &other.0, PRECISION);
        finish(if self.0.is_negative() == other.0.is_negative() {
            result
        } else {
            -result
        })
    }

    fn div_mod(&self, other: &Self) -> Option<(BigInt, BigDecimal)> {
        if other.0.is_zero() {
            return None;
        }
        let scale = scale_of(&self.0).max(scale_of(&other.0));
        let (a, b) = (mantissa_at(&self.0, scale), mantissa_at(&other.0, scale));
        Some((&a / &b, BigDecimal::new(a % b, scale)))
    }

    pub fn rem(&self, other: &Self) -> Option<Self> {
        finish(self.div_mod(other)?.1)
    }

    pub fn floor_div(&self, other: &Self) -> Option<Self> {
        finish(BigDecimal::new(self.div_mod(other)?.0, 0))
    }

    pub fn pow(&self, exponent: &Self) -> Option<Self> {
        let exponent = i64::try_from(&exponent.whole()?).ok()?;
        let magnitude = self.0.abs();
        let result = if magnitude.is_zero() {
            if exponent <= 0 {
                return None;
            }
            BigDecimal::zero()
        } else if exponent == 0 {
            BigDecimal::one()
        } else {
            power(&magnitude, exponent)?
        };
        finish(if self.0.is_negative() && exponent % 2 != 0 {
            -result
        } else {
            result
        })
    }

    pub fn round(&self, places: i64, mode: RoundingMode) -> Option<Self> {
        (-MAX_EXPONENT..=MAX_EXPONENT)
            .contains(&places)
            .then(|| Self(self.0.with_scale_round(places, mode)))
    }

    pub fn neg(&self) -> Self {
        Self(-self.0.clone())
    }

    pub fn abs(&self) -> Self {
        Self(self.0.abs())
    }

    pub fn compare(&self, other: &Self) -> Ordering {
        self.0.cmp(&other.0)
    }

    fn whole(&self) -> Option<BigInt> {
        let whole = self.0.with_scale(0);
        (whole == self.0).then(|| whole.into_bigint_and_scale().0)
    }

    pub fn is_odd(&self) -> bool {
        self.whole().is_some_and(|whole| !(whole % 2u8).is_zero())
    }

    pub fn is_even(&self) -> bool {
        self.whole().is_some_and(|whole| (whole % 2u8).is_zero())
    }

    pub fn is_divisible_by(&self, divisor: &Self) -> bool {
        self.div_mod(divisor)
            .is_some_and(|(_, rest)| rest.is_zero())
    }

    pub fn to_i128(&self) -> Option<i128> {
        i128::try_from(&mantissa_at(&self.0, 0)).ok()
    }

    pub fn to_f64(&self) -> f64 {
        self.to_string().parse().unwrap_or(f64::NAN)
    }
}

impl fmt::Display for Decimal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let (mantissa, scale) = self.0.as_bigint_and_scale();
        let digits = mantissa.magnitude().to_string();
        if mantissa.is_negative() {
            f.write_str("-")?;
        }
        if scale <= 0 {
            f.write_str(&digits)?;
            if !mantissa.is_zero() {
                f.write_str(&"0".repeat(scale.unsigned_abs() as usize))?;
            }
            return Ok(());
        }
        let scale = scale as usize;
        if digits.len() > scale {
            let (whole, fraction) = digits.split_at(digits.len() - scale);
            write!(f, "{whole}.{fraction}")
        } else {
            write!(f, "0.{}{digits}", "0".repeat(scale - digits.len()))
        }
    }
}
