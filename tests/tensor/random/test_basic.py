import pickle
from copy import copy

import numpy as np
import pytest
import scipy.stats as stats

import aesara.tensor as at
from aesara import function, shared
from aesara.compile.mode import Mode
from aesara.compile.sharedvalue import SharedVariable
from aesara.configdefaults import config
from aesara.graph.basic import Constant, Variable, graph_inputs
from aesara.graph.fg import FunctionGraph
from aesara.graph.op import get_test_value
from aesara.graph.optdb import OptimizationQuery
from aesara.tensor.basic_opt import ShapeFeature
from aesara.tensor.random.basic import (
    bernoulli,
    beta,
    betabinom,
    binomial,
    broadcast_shapes,
    categorical,
    cauchy,
    chisquare,
    choice,
    dirichlet,
    exponential,
    gamma,
    geometric,
    gumbel,
    halfcauchy,
    halfnormal,
    hypergeometric,
    integers,
    invgamma,
    laplace,
    logistic,
    lognormal,
    multinomial,
    multivariate_normal,
    nbinom,
    normal,
    pareto,
    permutation,
    poisson,
    randint,
    standard_normal,
    triangular,
    truncexpon,
    uniform,
    vonmises,
    wald,
    weibull,
)
from aesara.tensor.type import iscalar, scalar, tensor
from tests.unittest_tools import create_aesara_param


opts = OptimizationQuery(include=[None], exclude=["cxx_only", "BlasOpt"])
py_mode = Mode("py", opts)


def fixed_scipy_rvs(rvs_name):
    def _rvs(*args, size=None, **kwargs):
        res = getattr(stats, rvs_name).rvs(*args, size=size, **kwargs)
        res = np.broadcast_to(
            res,
            size
            if size is not None
            else broadcast_shapes(*[np.shape(a) for a in args]),
        )
        return res

    return _rvs


def rv_numpy_tester(rv, *params, rng=None, test_fn=None, **kwargs):
    """Test for correspondence between `RandomVariable` and NumPy shape and
    broadcast dimensions.
    """
    if rng is None:
        rng = np.random.default_rng()

    if test_fn is None:
        name = getattr(rv, "name", None)

        if name is None:
            name = rv.__name__

        def test_fn(*args, random_state=None, **kwargs):
            return getattr(random_state, name)(*args, **kwargs)

    param_vals = [get_test_value(p) if isinstance(p, Variable) else p for p in params]
    kwargs_vals = {
        k: get_test_value(v) if isinstance(v, Variable) else v
        for k, v in kwargs.items()
    }

    at_rng = shared(rng, borrow=True)

    numpy_res = np.asarray(test_fn(*param_vals, random_state=copy(rng), **kwargs_vals))

    aesara_res = rv(*params, rng=at_rng, **kwargs)

    assert aesara_res.type.numpy_dtype.kind == numpy_res.dtype.kind

    numpy_shape = np.shape(numpy_res)
    numpy_bcast = [s == 1 for s in numpy_shape]
    np.testing.assert_array_equal(aesara_res.type.broadcastable, numpy_bcast)

    fn_inputs = [
        i
        for i in graph_inputs([aesara_res])
        if not isinstance(i, (Constant, SharedVariable))
    ]
    aesara_fn = function(fn_inputs, aesara_res, mode=py_mode)

    aesara_res_val = aesara_fn()

    np.testing.assert_array_equal(aesara_res_val.shape, numpy_res.shape)

    np.testing.assert_allclose(aesara_res_val, numpy_res)


@pytest.mark.parametrize(
    "u, l, size",
    [
        (np.array(10, dtype=config.floatX), np.array(20, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), np.array(20, dtype=config.floatX), []),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(20, dtype=config.floatX),
            None,
        ),
    ],
)
def test_uniform_samples(u, l, size):
    rv_numpy_tester(uniform, u, l, size=size)


def test_uniform_default_args():
    rv_numpy_tester(uniform)


@pytest.mark.parametrize(
    "left, mode, right, size",
    [
        (
            np.array(10, dtype=config.floatX),
            np.array(12, dtype=config.floatX),
            np.array(20, dtype=config.floatX),
            None,
        ),
        (
            np.array(10, dtype=config.floatX),
            np.array(12, dtype=config.floatX),
            np.array(20, dtype=config.floatX),
            [],
        ),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(12, dtype=config.floatX),
            np.array(20, dtype=config.floatX),
            None,
        ),
    ],
)
def test_triangular_samples(left, mode, right, size):
    rv_numpy_tester(triangular, left, mode, right, size=size)


@pytest.mark.parametrize(
    "a, b, size",
    [
        (np.array(0.5, dtype=config.floatX), np.array(0.5, dtype=config.floatX), None),
        (np.array(0.5, dtype=config.floatX), np.array(0.5, dtype=config.floatX), []),
        (
            np.full((1, 2), 0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_beta_samples(a, b, size):
    rv_numpy_tester(beta, a, b, size=size)


M_at = iscalar("M")
M_at.tag.test_value = 3
sd_at = scalar("sd")
sd_at.tag.test_value = np.array(1.0, dtype=config.floatX)


@pytest.mark.parametrize(
    "M, sd, size",
    [
        (at.as_tensor_variable(np.array(1.0, dtype=config.floatX)), sd_at, ()),
        (
            at.as_tensor_variable(np.array(1.0, dtype=config.floatX)),
            sd_at,
            (M_at,),
        ),
        (
            at.as_tensor_variable(np.array(1.0, dtype=config.floatX)),
            sd_at,
            (2, M_at),
        ),
        (at.zeros((M_at,)), sd_at, ()),
        (at.zeros((M_at,)), sd_at, (M_at,)),
        (at.zeros((M_at,)), sd_at, (2, M_at)),
        (at.zeros((M_at,)), at.ones((M_at,)), ()),
        (at.zeros((M_at,)), at.ones((M_at,)), (2, M_at)),
        (
            create_aesara_param(
                np.array([[-1, 20], [300, -4000]], dtype=config.floatX)
            ),
            create_aesara_param(np.array([[1e-6, 2e-6]], dtype=config.floatX)),
            (3, 2, 2),
        ),
        (
            create_aesara_param(np.array([1], dtype=config.floatX)),
            create_aesara_param(np.array([10], dtype=config.floatX)),
            (1, 2),
        ),
    ],
)
def test_normal_infer_shape(M, sd, size):
    rv = normal(M, sd, size=size)
    rv_shape = list(normal._infer_shape(size or (), [M, sd], None))

    all_args = (M, sd) + size
    fn_inputs = [
        i
        for i in graph_inputs([a for a in all_args if isinstance(a, Variable)])
        if not isinstance(i, (Constant, SharedVariable))
    ]
    aesara_fn = function(
        fn_inputs, [at.as_tensor(o) for o in rv_shape + [rv]], mode=py_mode
    )

    *rv_shape_val, rv_val = aesara_fn(
        *[
            i.tag.test_value
            for i in fn_inputs
            if not isinstance(i, (SharedVariable, Constant))
        ]
    )

    assert tuple(rv_shape_val) == tuple(rv_val.shape)


@config.change_flags(compute_test_value="raise")
def test_normal_ShapeFeature():
    M_at = iscalar("M")
    M_at.tag.test_value = 3
    sd_at = scalar("sd")
    sd_at.tag.test_value = np.array(1.0, dtype=config.floatX)

    d_rv = normal(at.ones((M_at,)), sd_at, size=(2, M_at))
    d_rv.tag.test_value

    fg = FunctionGraph(
        [i for i in graph_inputs([d_rv]) if not isinstance(i, Constant)],
        [d_rv],
        clone=False,
        features=[ShapeFeature()],
    )
    s1, s2 = fg.shape_feature.shape_of[d_rv]

    assert get_test_value(s1) == get_test_value(d_rv).shape[0]
    assert get_test_value(s2) == get_test_value(d_rv).shape[1]


@pytest.mark.parametrize(
    "mean, sigma, size",
    [
        (np.array(100, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), None),
        (np.array(100, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), []),
        (
            np.full((1, 2), 100, dtype=config.floatX),
            np.array(1e-2, dtype=config.floatX),
            None,
        ),
    ],
)
def test_normal_samples(mean, sigma, size):
    rv_numpy_tester(normal, mean, sigma, size=size)


def test_normal_default_args():
    rv_numpy_tester(standard_normal)


@pytest.mark.parametrize(
    "mean, sigma, size",
    [
        (np.array(100, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), None),
        (np.array(100, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), []),
        (
            np.full((1, 2), 100, dtype=config.floatX),
            np.array(1e-2, dtype=config.floatX),
            None,
        ),
    ],
)
def test_halfnormal_samples(mean, sigma, size):
    rv_numpy_tester(
        halfnormal, mean, sigma, size=size, test_fn=fixed_scipy_rvs("halfnorm")
    )


@pytest.mark.parametrize(
    "mean, sigma, size",
    [
        (np.array(10, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), np.array(1e-2, dtype=config.floatX), []),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(1e-2, dtype=config.floatX),
            None,
        ),
    ],
)
def test_lognormal_samples(mean, sigma, size):
    rv_numpy_tester(lognormal, mean, sigma, size=size)


@pytest.mark.parametrize(
    "a, b, size",
    [
        (np.array(0.5, dtype=config.floatX), np.array(0.5, dtype=config.floatX), None),
        (np.array(0.5, dtype=config.floatX), np.array(0.5, dtype=config.floatX), []),
        (
            np.full((1, 2), 0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_gamma_samples(a, b, size):
    gamma_test_fn = fixed_scipy_rvs("gamma")

    def test_fn(shape, rate, **kwargs):
        return gamma_test_fn(shape, scale=1.0 / rate, **kwargs)

    rv_numpy_tester(
        gamma,
        a,
        b,
        size=size,
        test_fn=test_fn,
    )


@pytest.mark.parametrize(
    "df, size",
    [
        (np.array(2, dtype=config.floatX), None),
        (np.array(2, dtype=config.floatX), []),
        (np.full((1, 2), 2, dtype=np.int64), None),
    ],
)
def test_chisquare_samples(df, size):
    rv_numpy_tester(chisquare, df, size=size, test_fn=fixed_scipy_rvs("chi2"))


@pytest.mark.parametrize(
    "mu, beta, size",
    [
        (np.array(0, dtype=config.floatX), np.array(1, dtype=config.floatX), None),
        (np.array(0, dtype=config.floatX), np.array(1, dtype=config.floatX), []),
        (
            np.full((1, 2), 0, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_gumbel_samples(mu, beta, size):
    rv_numpy_tester(gumbel, mu, beta, size=size, test_fn=fixed_scipy_rvs("gumbel_r"))


@pytest.mark.parametrize(
    "lam, size",
    [
        (np.array(10, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), []),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            None,
        ),
    ],
)
def test_exponential_samples(lam, size):
    rv_numpy_tester(exponential, lam, size=size)


def test_exponential_default_args():
    rv_numpy_tester(exponential)


@pytest.mark.parametrize(
    "alpha, size",
    [
        (np.array(10, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), []),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            None,
        ),
    ],
)
def test_weibull_samples(alpha, size):
    rv_numpy_tester(weibull, alpha, size=size)


@pytest.mark.parametrize(
    "loc, scale, size",
    [
        (np.array(2, dtype=config.floatX), np.array(0.5, dtype=config.floatX), None),
        (np.array(2, dtype=config.floatX), np.array(0.5, dtype=config.floatX), []),
        (
            np.full((1, 2), 2, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_logistic_samples(loc, scale, size):
    rv_numpy_tester(logistic, loc, scale, size=size)


def test_logistic_default_args():
    rv_numpy_tester(logistic)


@pytest.mark.parametrize(
    "mu, kappa, size",
    [
        (
            np.array(np.pi, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
        (np.array(np.pi, dtype=config.floatX), np.array(0.5, dtype=config.floatX), []),
        (
            np.full((1, 2), np.pi, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_vonmises_samples(mu, kappa, size):
    rv_numpy_tester(vonmises, mu, kappa, size=size)


@pytest.mark.parametrize(
    "alpha, size",
    [
        (np.array(0.5, dtype=config.floatX), None),
        (np.array(0.5, dtype=config.floatX), []),
        (
            np.full((1, 2), 0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_pareto_samples(alpha, size):
    rv_numpy_tester(pareto, alpha, size=size, test_fn=fixed_scipy_rvs("pareto"))


def mvnormal_test_fn(mean=None, cov=None, size=None, random_state=None):
    if mean is None:
        mean = np.array([0.0], dtype=config.floatX)
    if cov is None:
        cov = np.array([[1.0]], dtype=config.floatX)
    if size is None:
        size = ()
    return multivariate_normal.rng_fn(random_state, mean, cov, size)


@pytest.mark.parametrize(
    "mu, cov, size",
    [
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            None,
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [1],
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [4],
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [4, 1],
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [4, 1, 1],
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [1, 4, 1],
        ),
        (
            np.array([0], dtype=config.floatX),
            np.eye(1, dtype=config.floatX),
            [1, 5, 8],
        ),
        (
            np.array([0, 1, 2], dtype=config.floatX),
            np.diag(
                np.array([1, 10, 100], dtype=config.floatX),
            ),
            None,
        ),
        (
            np.array([0, 1, 2], dtype=config.floatX),
            np.stack(
                [
                    np.eye(3, dtype=config.floatX),
                    np.eye(3, dtype=config.floatX) * 10.0,
                ]
            ),
            [2, 3, 2],
        ),
        (
            np.array([[0, 1, 2], [4, 5, 6]], dtype=config.floatX),
            np.diag(
                np.array([1, 10, 100], dtype=config.floatX),
            ),
            None,
        ),
        (
            np.array([[0, 1, 2], [4, 5, 6]], dtype=config.floatX),
            np.stack(
                [
                    np.eye(3, dtype=config.floatX),
                    np.eye(3, dtype=config.floatX) * 10.0,
                ]
            ),
            [2, 3, 2, 2],
        ),
        (
            np.array([[0], [10], [100]], dtype=config.floatX),
            np.eye(1, dtype=config.floatX) * 1e-6,
            [2, 3, 3],
        ),
    ],
)
def test_mvnormal_samples(mu, cov, size):
    rv_numpy_tester(multivariate_normal, mu, cov, size=size, test_fn=mvnormal_test_fn)


def test_mvnormal_default_args():
    rv_numpy_tester(multivariate_normal, test_fn=mvnormal_test_fn)

    with pytest.raises(ValueError, match="shape mismatch.*"):
        multivariate_normal.rng_fn(
            None, np.zeros((1, 2)), np.ones((1, 2, 2)), size=(4,)
        )


@config.change_flags(compute_test_value="raise")
def test_mvnormal_ShapeFeature():
    M_at = iscalar("M")
    M_at.tag.test_value = 2

    d_rv = multivariate_normal(at.ones((M_at,)), at.eye(M_at), size=2)

    fg = FunctionGraph(
        [i for i in graph_inputs([d_rv]) if not isinstance(i, Constant)],
        [d_rv],
        clone=False,
        features=[ShapeFeature()],
    )

    s1, s2 = fg.shape_feature.shape_of[d_rv]

    assert get_test_value(s1) == 2
    assert M_at in graph_inputs([s2])

    # Test broadcasted shapes
    mean = tensor(config.floatX, [True, False])
    mean.tag.test_value = np.array([[0, 1, 2]], dtype=config.floatX)

    test_covar = np.diag(np.array([1, 10, 100], dtype=config.floatX))
    test_covar = np.stack([test_covar, test_covar * 10.0])
    cov = at.as_tensor(test_covar).type()
    cov.tag.test_value = test_covar

    d_rv = multivariate_normal(mean, cov, size=[2, 3, 2])

    fg = FunctionGraph(
        outputs=[d_rv],
        clone=False,
        features=[ShapeFeature()],
    )

    s1, s2, s3, s4 = fg.shape_feature.shape_of[d_rv]

    assert s1.get_test_value() == 2
    assert s2.get_test_value() == 3
    assert s3.get_test_value() == 2
    assert s4.get_test_value() == 3


@pytest.mark.parametrize(
    "alphas, size",
    [
        (np.array([[100, 1, 1], [1, 100, 1], [1, 1, 100]], dtype=config.floatX), None),
        (
            np.array([[100, 1, 1], [1, 100, 1], [1, 1, 100]], dtype=config.floatX),
            (10, 3),
        ),
        (
            np.array([[100, 1, 1], [1, 100, 1], [1, 1, 100]], dtype=config.floatX),
            (10, 2, 3),
        ),
    ],
)
def test_dirichlet_samples(alphas, size):
    def dirichlet_test_fn(mean=None, cov=None, size=None, random_state=None):
        if size is None:
            size = ()
        return dirichlet.rng_fn(random_state, alphas, size)

    rv_numpy_tester(dirichlet, alphas, size=size, test_fn=dirichlet_test_fn)


def test_dirichlet_rng():
    alphas = np.array([[100, 1, 1], [1, 100, 1], [1, 1, 100]], dtype=config.floatX)

    with pytest.raises(ValueError, match="shape mismatch.*"):
        # The independent dimension's shape is missing from size (i.e. should
        # be `(10, 2, 3)`)
        dirichlet.rng_fn(None, alphas, size=(10, 2))


M_at = iscalar("M")
M_at.tag.test_value = 3


@pytest.mark.parametrize(
    "M, size",
    [
        (at.ones((M_at,)), ()),
        (at.ones((M_at,)), (M_at + 1,)),
        (at.ones((M_at,)), (2, M_at)),
        (at.ones((M_at, M_at + 1)), ()),
        (at.ones((M_at, M_at + 1)), (M_at + 2, M_at)),
        (at.ones((M_at, M_at + 1)), (2, M_at + 2, M_at + 3, M_at)),
    ],
)
def test_dirichlet_infer_shape(M, size):
    rv = dirichlet(M, size=size)
    rv_shape = list(dirichlet._infer_shape(size or (), [M], None))

    all_args = (M,) + size
    fn_inputs = [
        i
        for i in graph_inputs([a for a in all_args if isinstance(a, Variable)])
        if not isinstance(i, (Constant, SharedVariable))
    ]
    aesara_fn = function(
        fn_inputs, [at.as_tensor(o) for o in rv_shape + [rv]], mode=py_mode
    )

    *rv_shape_val, rv_val = aesara_fn(
        *[
            i.tag.test_value
            for i in fn_inputs
            if not isinstance(i, (SharedVariable, Constant))
        ]
    )

    assert tuple(rv_shape_val) == tuple(rv_val.shape)


@config.change_flags(compute_test_value="raise")
def test_dirichlet_ShapeFeature():
    """Make sure `RandomVariable.infer_shape` works with `ShapeFeature`."""
    M_at = iscalar("M")
    M_at.tag.test_value = 2
    N_at = iscalar("N")
    N_at.tag.test_value = 3

    d_rv = dirichlet(at.ones((M_at, N_at)), name="Gamma")

    fg = FunctionGraph(
        outputs=[d_rv],
        clone=False,
        features=[ShapeFeature()],
    )

    s1, s2 = fg.shape_feature.shape_of[d_rv]

    assert M_at in graph_inputs([s1])
    assert N_at in graph_inputs([s2])


@pytest.mark.parametrize(
    "lam, size",
    [
        (np.array(10, dtype=np.int64), None),
        (np.array(10, dtype=np.int64), []),
        (
            np.full((1, 2), 10, dtype=np.int64),
            None,
        ),
    ],
)
def test_poisson_samples(lam, size):
    rv_numpy_tester(poisson, lam, size=size)


def test_poisson_default_args():
    rv_numpy_tester(poisson)


@pytest.mark.parametrize(
    "p, size",
    [
        (np.array(0.1, dtype=config.floatX), None),
        (np.array(0.1, dtype=config.floatX), []),
        (
            np.full((1, 2), 0.1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_geometric_samples(p, size):
    rv_numpy_tester(geometric, p, size=size)


@pytest.mark.parametrize(
    "ngood, nbad, nsample, size",
    [
        (
            np.array(10, dtype=np.int64),
            np.array(20, dtype=np.int64),
            np.array(5, dtype=np.int64),
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(20, dtype=np.int64),
            np.array(5, dtype=np.int64),
            [],
        ),
        (
            np.full((1, 2), 10, dtype=np.int64),
            np.array(20, dtype=np.int64),
            np.array(5, dtype=np.int64),
            None,
        ),
    ],
)
def test_hypergeometric_samples(ngood, nbad, nsample, size):
    rv_numpy_tester(hypergeometric, ngood, nbad, nsample, size=size)


@pytest.mark.parametrize(
    "loc, scale, size",
    [
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), []),
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), [2, 3]),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(0.1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_cauchy_samples(loc, scale, size):
    rv_numpy_tester(cauchy, loc, scale, size=size, test_fn=fixed_scipy_rvs("cauchy"))


def test_cauchy_default_args():
    rv_numpy_tester(cauchy, test_fn=stats.cauchy.rvs)


@pytest.mark.parametrize(
    "loc, scale, size",
    [
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), []),
        (np.array(10, dtype=config.floatX), np.array(0.1, dtype=config.floatX), [2, 3]),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(0.1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_halfcauchy_samples(loc, scale, size):
    rv_numpy_tester(
        halfcauchy, loc, scale, size=size, test_fn=fixed_scipy_rvs("halfcauchy")
    )


def test_halfcauchy_default_args():
    rv_numpy_tester(halfcauchy, test_fn=stats.halfcauchy.rvs)


@pytest.mark.parametrize(
    "loc, scale, size",
    [
        (np.array(2, dtype=config.floatX), np.array(1, dtype=config.floatX), None),
        (np.array(2, dtype=config.floatX), np.array(1, dtype=config.floatX), []),
        (np.array(2, dtype=config.floatX), np.array(1, dtype=config.floatX), [2, 3]),
        (
            np.full((1, 2), 2, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_invgamma_samples(loc, scale, size):
    rv_numpy_tester(
        invgamma,
        loc,
        scale,
        size=size,
        test_fn=lambda *args, size=None, random_state=None, **kwargs: invgamma.rng_fn(
            random_state, *(args + (size,))
        ),
    )


@pytest.mark.parametrize(
    "mean, scale, size",
    [
        (np.array(10, dtype=config.floatX), np.array(1, dtype=config.floatX), None),
        (np.array(10, dtype=config.floatX), np.array(1, dtype=config.floatX), []),
        (np.array(10, dtype=config.floatX), np.array(1, dtype=config.floatX), [2, 3]),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_wald_samples(mean, scale, size):
    rv_numpy_tester(wald, mean, scale, size=size)


@pytest.mark.parametrize(
    "b, loc, scale, size",
    [
        (
            np.array(5, dtype=config.floatX),
            np.array(0, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            None,
        ),
        (
            np.array(5, dtype=config.floatX),
            np.array(0, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            [],
        ),
        (
            np.array(5, dtype=config.floatX),
            np.array(0, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 5, dtype=config.floatX),
            np.array(0, dtype=config.floatX),
            np.array(1, dtype=config.floatX),
            None,
        ),
    ],
)
def test_truncexpon_samples(b, loc, scale, size):
    rv_numpy_tester(
        truncexpon,
        b,
        loc,
        scale,
        size=size,
        test_fn=lambda *args, size=None, random_state=None, **kwargs: truncexpon.rng_fn(
            random_state, *(args + (size,))
        ),
    )


@pytest.mark.parametrize(
    "p, size",
    [
        (
            np.array(0.5, dtype=config.floatX),
            None,
        ),
        (
            np.array(0.5, dtype=config.floatX),
            [],
        ),
        (
            np.array(0.5, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_bernoulli_samples(p, size):
    rv_numpy_tester(
        bernoulli,
        p,
        size=size,
        test_fn=lambda *args, size=None, random_state=None, **kwargs: bernoulli.rng_fn(
            random_state, *(args + (size,))
        ),
    )


@pytest.mark.parametrize(
    "loc, scale, size",
    [
        (
            np.array(10, dtype=config.floatX),
            np.array(5, dtype=config.floatX),
            None,
        ),
        (
            np.array(10, dtype=config.floatX),
            np.array(5, dtype=config.floatX),
            [],
        ),
        (
            np.array(10, dtype=config.floatX),
            np.array(5, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 10, dtype=config.floatX),
            np.array(5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_laplace_samples(loc, scale, size):
    rv_numpy_tester(laplace, loc, scale, size=size)


@pytest.mark.parametrize(
    "M, p, size",
    [
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            [],
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_binomial_samples(M, p, size):
    rv_numpy_tester(binomial, M, p, size=size)


@pytest.mark.parametrize(
    "M, p, size",
    [
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            [],
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_nbinom_samples(M, p, size):
    rv_numpy_tester(
        nbinom,
        M,
        p,
        size=size,
        test_fn=lambda *args, size=None, random_state=None, **kwargs: nbinom.rng_fn(
            random_state, *(args + (size,))
        ),
    )


@pytest.mark.parametrize(
    "M, a, p, size",
    [
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            [],
        ),
        (
            np.array(10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            [2, 3],
        ),
        (
            np.full((1, 2), 10, dtype=np.int64),
            np.array(0.5, dtype=config.floatX),
            np.array(0.5, dtype=config.floatX),
            None,
        ),
    ],
)
def test_betabinom_samples(M, a, p, size):
    rv_numpy_tester(
        betabinom,
        M,
        a,
        p,
        size=size,
        test_fn=lambda *args, size=None, random_state=None, **kwargs: betabinom.rng_fn(
            random_state, *(args + (size,))
        ),
    )


@pytest.mark.parametrize(
    "M, p, size, test_fn",
    [
        (
            np.array(10, dtype=np.int64),
            np.array([0.7, 0.3], dtype=config.floatX),
            None,
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array([0.7, 0.3], dtype=config.floatX),
            [],
            None,
        ),
        (
            np.array(10, dtype=np.int64),
            np.array([0.7, 0.3], dtype=config.floatX),
            [2, 3],
            None,
        ),
        (
            np.full((1, 2), 10, dtype=np.int64),
            np.array([0.7, 0.3], dtype=config.floatX),
            None,
            lambda *args, size=None, random_state=None, **kwargs: multinomial.rng_fn(
                random_state, *(args + (size,))
            ),
        ),
        (
            np.array([10, 20], dtype=np.int64),
            np.array([[0.999, 0.001], [0.001, 0.999]], dtype=config.floatX),
            None,
            lambda *args, **kwargs: np.array([[10, 0], [0, 20]]),
        ),
        (
            np.array([10, 20], dtype=np.int64),
            np.array([[0.999, 0.001], [0.001, 0.999]], dtype=config.floatX),
            (3, 2),
            lambda *args, **kwargs: np.stack([np.array([[10, 0], [0, 20]])] * 3),
        ),
    ],
)
def test_multinomial_samples(M, p, size, test_fn):
    rng = np.random.default_rng(1234)
    rv_numpy_tester(
        multinomial,
        M,
        p,
        size=size,
        test_fn=test_fn,
        rng=rng,
    )


def test_multinomial_rng():
    test_M = np.array([10, 20], dtype=np.int64)
    test_p = np.array([[0.999, 0.001], [0.001, 0.999]], dtype=config.floatX)

    with pytest.raises(ValueError, match="shape mismatch.*"):
        # The independent dimension's shape is missing from size (i.e. should
        # be `(1, 2)`)
        multinomial.rng_fn(None, test_M, test_p, size=(1,))


@pytest.mark.parametrize(
    "p, size, test_fn",
    [
        (
            np.array([100000, 1, 1], dtype=config.floatX),
            None,
            lambda *args, **kwargs: np.array(0, dtype=np.int64),
        ),
        (
            np.array(
                [[100000, 1, 1], [1, 100000, 1], [1, 1, 100000]], dtype=config.floatX
            ),
            (10, 3),
            lambda *args, **kwargs: np.tile(np.arange(3).astype(np.int64), (10, 1)),
        ),
        (
            np.array(
                [[100000, 1, 1], [1, 100000, 1], [1, 1, 100000]], dtype=config.floatX
            ),
            (10, 2, 3),
            lambda *args, **kwargs: np.tile(np.arange(3).astype(np.int64), (10, 2, 1)),
        ),
    ],
)
def test_categorical_samples(p, size, test_fn):
    p = p / p.sum(axis=-1)
    rng = np.random.default_rng(232)

    rv_numpy_tester(
        categorical,
        p,
        size=size,
        test_fn=test_fn,
        rng=rng,
    )


def test_categorical_basic():
    p = np.array([[100000, 1, 1], [1, 100000, 1], [1, 1, 100000]], dtype=config.floatX)
    p = p / p.sum(axis=-1)

    rng = np.random.default_rng()

    with pytest.raises(ValueError):
        categorical.rng_fn(rng, p, size=10)


def test_randint_samples():

    with pytest.raises(TypeError):
        randint(10, rng=shared(np.random.default_rng()))

    rng = np.random.RandomState(2313)
    rv_numpy_tester(randint, 10, None, rng=rng)
    rv_numpy_tester(randint, 0, 1, rng=rng)
    rv_numpy_tester(randint, 0, 1, size=[3], rng=rng)
    rv_numpy_tester(randint, [0, 1, 2], 5, rng=rng)
    rv_numpy_tester(randint, [0, 1, 2], 5, size=[3, 3], rng=rng)
    rv_numpy_tester(randint, [0], [5], size=[1], rng=rng)
    rv_numpy_tester(randint, at.as_tensor_variable([-1]), [1], size=[1], rng=rng)
    rv_numpy_tester(
        randint,
        at.as_tensor_variable([-1]),
        [1],
        size=at.as_tensor_variable([1]),
        rng=rng,
    )


def test_integers_samples():

    with pytest.raises(TypeError):
        integers(10, rng=shared(np.random.RandomState()))

    rng = np.random.default_rng(2313)
    rv_numpy_tester(integers, 10, None, rng=rng)
    rv_numpy_tester(integers, 0, 1, rng=rng)
    rv_numpy_tester(integers, 0, 1, size=[3], rng=rng)
    rv_numpy_tester(integers, [0, 1, 2], 5, rng=rng)
    rv_numpy_tester(integers, [0, 1, 2], 5, size=[3, 3], rng=rng)
    rv_numpy_tester(integers, [0], [5], size=[1], rng=rng)
    rv_numpy_tester(integers, at.as_tensor_variable([-1]), [1], size=[1], rng=rng)
    rv_numpy_tester(
        integers,
        at.as_tensor_variable([-1]),
        [1],
        size=at.as_tensor_variable([1]),
        rng=rng,
    )


def test_choice_samples():
    with pytest.raises(NotImplementedError):
        choice._supp_shape_from_params(np.asarray(5))

    rv_numpy_tester(choice, np.asarray([5]))
    rv_numpy_tester(choice, np.array([1.0, 5.0], dtype=config.floatX))
    rv_numpy_tester(choice, np.asarray([5]), 3)

    with pytest.raises(ValueError):
        rv_numpy_tester(choice, np.array([[1, 2], [3, 4]]))

    rv_numpy_tester(choice, [1, 2, 3], 1)
    rv_numpy_tester(choice, [1, 2, 3], 1, p=at.as_tensor([1 / 3.0, 1 / 3.0, 1 / 3.0]))
    rv_numpy_tester(choice, [1, 2, 3], (10, 2), replace=True)
    rv_numpy_tester(choice, at.as_tensor_variable([1, 2, 3]), 2, replace=True)


def test_permutation_samples():
    rv_numpy_tester(
        permutation,
        np.asarray(5),
        test_fn=lambda x, random_state=None: random_state.permutation(x.item()),
    )
    rv_numpy_tester(permutation, [1, 2, 3])
    rv_numpy_tester(permutation, [[1, 2], [3, 4]])
    rv_numpy_tester(permutation, np.array([1.0, 2.0, 3.0], dtype=config.floatX))


@config.change_flags(compute_test_value="off")
def test_pickle():
    # This is an interesting `Op` case, because it has `None` types and a
    # conditional dtype
    sample_a = choice(5, size=(2, 3))

    a_pkl = pickle.dumps(sample_a)
    a_unpkl = pickle.loads(a_pkl)

    assert a_unpkl.owner.op._props() == sample_a.owner.op._props()
