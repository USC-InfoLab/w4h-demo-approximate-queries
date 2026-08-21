"""Pure-Python tests for the coefficient-formatting and error-calculation logic
used in the notebook. No live Postgres/fft_approximate dependency — there's no
CI-friendly way to install a C extension in a plain test run, so these cover
the Python-side math only, matching what the notebook actually computes."""

import numpy as np
import pytest


def format_complex_literal(c: complex) -> str:
    """Matches the notebook's `f"({c.real}{c.imag:+}j)"` formatting."""
    return f"({c.real}{c.imag:+}j)"


def relative_error_pct(approx: float, exact: float) -> float:
    return abs(approx - exact) / abs(exact) * 100


def test_format_complex_literal_positive_imag():
    assert format_complex_literal(complex(1.5, 2.5)) == "(1.5+2.5j)"


def test_format_complex_literal_negative_imag_no_double_sign():
    # A naive f"{re}+{im}j" produces "(1.5+-2.5j)", which fft_approximate's
    # complex_in parser rejects (confirmed against the real extension).
    lit = format_complex_literal(complex(1.5, -2.5))
    assert lit == "(1.5-2.5j)"
    assert "+-" not in lit


def test_format_complex_literal_zero_imag():
    lit = format_complex_literal(complex(72000.0, 0.0))
    assert lit == "(72000.0+0.0j)"


def test_relative_error_pct_exact_match():
    assert relative_error_pct(103.472, 103.472) == 0.0


def test_relative_error_pct_known_case():
    # Matches a real observed run: K=1 coefficient, ~4.25% error.
    err = relative_error_pct(99.070, 103.472)
    assert 4.2 < err < 4.3


def test_fft_dc_coefficient_is_mean_times_length():
    # The extension's own test fixture (cohort_hr.sql) relies on this
    # identity: for a constant signal, the DC coefficient (k=0) equals
    # mean * signal_len, and approximate_avg(dc_only) recovers the mean
    # exactly. Verify the Python-side half of that identity with numpy.
    values = np.full(1000, 72.0)
    coeffs = np.fft.fft(values)
    assert coeffs[0].real == pytest.approx(72.0 * 1000, rel=1e-9)
    assert coeffs[0].imag == pytest.approx(0.0, abs=1e-6)


def test_truncated_coefficients_converge_toward_exact_mean():
    # More coefficients should not make accuracy worse on average — using
    # all N coefficients should reconstruct the signal's own window means
    # far more closely than a single (DC-only) coefficient does, for a
    # non-constant signal.
    rng = np.random.default_rng(42)
    values = 70 + 10 * np.sin(np.linspace(0, 6 * np.pi, 512)) + rng.normal(0, 1, 512)
    coeffs = np.fft.fft(values)
    exact = float(np.mean(values[100:400]))

    def approx_from_k(k_count: int) -> float:
        # Direct inverse relationship: reconstruct signal from truncated
        # coefficients (zero out the rest), then take the same window mean —
        # this mirrors what approximate_avg does with a WHERE k < K filter.
        truncated = np.zeros_like(coeffs)
        truncated[:k_count] = coeffs[:k_count]
        recon = np.fft.ifft(truncated).real
        return float(np.mean(recon[100:400]))

    err_1 = relative_error_pct(approx_from_k(1), exact)
    err_50 = relative_error_pct(approx_from_k(50), exact)
    assert err_50 < err_1
