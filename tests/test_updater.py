"""Property-based tests for BetaBinomialModel."""
from hypothesis import given, strategies as st

from flight_delay_bayes.bayes.updater import BetaBinomialModel


@given(
    alpha=st.floats(min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False),
    beta=st.floats(min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False),
    k=st.integers(min_value=1, max_value=100),
)
def test_posterior_mean_increases_after_late(alpha: float, beta: float, k: int) -> None:
    """Posterior mean of *late* probability should increase after observing late flights."""
    model = BetaBinomialModel(alpha, beta)
    prior_mean_late = model.alpha / (model.alpha + model.beta)

    for _ in range(k):
        model.update(1)  # observe late flight

    posterior_mean_late = model.alpha / (model.alpha + model.beta)
    assert posterior_mean_late > prior_mean_late 