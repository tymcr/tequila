import pytest, numpy
import tequila as tq
import multiprocessing as mp
from tequila.simulators.simulator_api import simulate
from tequila.optimizers.optimizer_gd import minimize


@pytest.mark.parametrize("simulator", [tq.simulators.simulator_api.pick_backend("random")])
@pytest.mark.parametrize('method', numpy.random.choice(tq.optimizers.optimizer_gd.OptimizerGD.available_methods(),1))
@pytest.mark.parametrize('options', [None, '2-point', {"method":"2-point", "stepsize": 1.e-4}, {"method":"2-point-forward", "stepsize": 1.e-4}, {"method":"2-point-backward", "stepsize": 1.e-4} ])
def test_execution(simulator,method, options):
    U = tq.gates.Rz(angle="a", target=0) \
        + tq.gates.X(target=2) \
        + tq.gates.Ry(angle="b", target=1, control=2) \
        + tq.gates.Trotterized(angles=["c", "d"],
                               generators=[-0.25 * tq.paulis.Z(1), tq.paulis.X(0) + tq.paulis.Y(1)], steps=2) \
        + tq.gates.Trotterized(angles=[1.0, 2.0],
                               generators=[-0.25 * tq.paulis.Z(1), tq.paulis.X(0) + tq.paulis.Y(1)], steps=2) \
        + tq.gates.ExpPauli(angle="a", paulistring="X(0)Y(1)Z(2)")

    H = 1.0 * tq.paulis.X(0) + 2.0 * tq.paulis.Y(1) + 3.0 * tq.paulis.Z(2)
    O = tq.ExpectationValue(U=U, H=H)
    result = minimize(objective=O,method=method, maxiter=1, backend=simulator, gradient=options)

@pytest.mark.parametrize("simulator", [tq.simulators.simulator_api.pick_backend("random", samples=1)])
@pytest.mark.parametrize('options', [None, '2-point', {"method":"2-point", "stepsize": 1.e-4}, {"method":"2-point-forward", "stepsize": 1.e-4}, {"method":"2-point-backward", "stepsize": 1.e-4} ])
def test_execution_shot(simulator, options):
    U = tq.gates.Rz(angle="a", target=0) \
        + tq.gates.X(target=2) \
        + tq.gates.Ry(angle="b", target=1, control=2) \
        + tq.gates.Trotterized(angles=["c","d"],
                               generators=[-0.25 * tq.paulis.Z(1), tq.paulis.X(0) + tq.paulis.Y(1)], steps=2) \
        + tq.gates.Trotterized(angles=[1.0, 2.0],
                               generators=[-0.25 * tq.paulis.Z(1), tq.paulis.X(0) + tq.paulis.Y(1)], steps=2) \
        + tq.gates.ExpPauli(angle="a", paulistring="X(0)Y(1)Z(2)")
    H = 1.0 * tq.paulis.X(0) + 2.0 * tq.paulis.Y(1) + 3.0 * tq.paulis.Z(2)
    O = tq.ExpectationValue(U=U, H=H)
    mi=2
    result = minimize(objective=O, maxiter=mi, backend=simulator,samples=10, gradient=options)

@pytest.mark.parametrize("simulator", [tq.simulators.simulator_api.pick_backend("random")])
@pytest.mark.parametrize('method', tq.optimizers.optimizer_gd.OptimizerGD.available_methods())
def test_method_convergence(simulator,method):
    U = tq.gates.Trotterized(angles=["a"], steps=1, generators=[tq.paulis.Y(0)])
    H = tq.paulis.X(0)
    O = tq.ExpectationValue(U=U, H=H)
    samples=None
    angles={'a':numpy.pi/3}
    result = minimize(objective=O, method=method,initial_values=angles, samples=samples, lr=0.1,maxiter=200, backend=simulator)
    assert (numpy.isclose(result.energy, -1.0,atol=3.e-2))

@pytest.mark.parametrize("simulator", [tq.simulators.simulator_api.pick_backend()])
@pytest.mark.parametrize("method", tq.optimizers.optimizer_gd.OptimizerGD.available_methods())
def test_methods_qng(simulator, method):
    ### please note! I am finely tuned to always pass! don't get cocky and change lr, maxiter, etc.
    H = tq.paulis.Y(0)
    U = tq.gates.Ry(numpy.pi/4,0) +tq.gates.Ry(numpy.pi/3,1)+tq.gates.Ry(numpy.pi/7,2)
    U += tq.gates.Rz('a',0)+tq.gates.Rz('b',1)
    U += tq.gates.CNOT(control=0,target=1)+tq.gates.CNOT(control=1,target=2)
    U += tq.gates.Ry('c',1) +tq.gates.Rx('d',2)
    U += tq.gates.CNOT(control=0,target=1)+tq.gates.CNOT(control=1,target=2)
    E = tq.ExpectationValue(H=H, U=U)
    # just equal to the original circuit, but i'm checking that all the sub-division works
    O=E
    initial_values = {"a": 0.432, "b": -0.123, 'c':0.543,'d':0.233}

    lr=0.1
    result = minimize(objective=-O,gradient='qng',backend=simulator,
                                         method=method, maxiter=200,lr=lr,
                                         initial_values=initial_values, silent=False)
    assert(numpy.isclose(result.energy, -0.612, atol=2.e-2))

