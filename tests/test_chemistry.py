import pytest
import tequila.quantumchemistry as qc
import numpy
import os, glob

import tequila.simulators.simulator_api
from tequila.objective import ExpectationValue
from tequila.simulators.simulator_api import simulate

import tequila as tq

def teardown_function(function):
    [os.remove(x) for x in glob.glob("data/*.pickle")]
    [os.remove(x) for x in glob.glob("data/*.out")]
    [os.remove(x) for x in glob.glob("data/*.hdf5")]
    [os.remove(x) for x in glob.glob("*.clean")]
    [os.remove(x) for x in glob.glob("data/*.npy")]
    [os.remove(x) for x in glob.glob("*.npy")]
    [os.remove(x) for x in glob.glob("qvm.log")]
    [os.remove(x) for x in glob.glob("*.dat")]

@pytest.mark.dependencies
def test_dependencies():
    assert(tq.chemistry.has_psi4)

@pytest.mark.skipif(condition=len(qc.INSTALLED_QCHEMISTRY_BACKENDS) == 0,
                    reason="no quantum chemistry backends installed")
def test_interface():
    molecule = tq.chemistry.Molecule(basis_set='sto-3g', geometry="data/h2.xyz", transformation="JW")


@pytest.mark.skipif(condition=not (qc.has_pyscf and qc.has_psi4),
                    reason="you don't have a quantum chemistry backend installed")
@pytest.mark.parametrize("geom", [" H 0.0 0.0 1.0\n H 0.0 0.0 -1.0", " he 0.0 0.0 0.0", " be 0.0 0.0 0.0"])
@pytest.mark.parametrize("basis", ["sto-3g"])
@pytest.mark.parametrize("trafo", ["JW", "BK"])
def test_hamiltonian_consistency(geom: str, basis: str, trafo: str):
    parameters_qc = qc.ParametersQC(geometry=geom, basis_set=basis, outfile="asd")
    hqc1 = qc.QuantumChemistryPsi4(parameters=parameters_qc).make_hamiltonian(transformation=trafo)
    hqc2 = qc.QuantumChemistryPySCF(parameters=parameters_qc).make_hamiltonian(transformation=trafo)
    assert (hqc1.qubit_operator == hqc2.qubit_operator)


@pytest.mark.skipif(condition=not qc.has_psi4, reason="you don't have psi4")
def test_h2_hamiltonian_psi4():
    do_test_h2_hamiltonian(qc_interface=qc.QuantumChemistryPsi4)


@pytest.mark.skipif(condition=not qc.has_pyscf, reason="you don't have pyscf")
def test_h2_hamiltonian_pysf():
    do_test_h2_hamiltonian(qc_interface=qc.QuantumChemistryPySCF)


def do_test_h2_hamiltonian(qc_interface):
    parameters = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    H = qc_interface(parameters=parameters).make_hamiltonian().to_matrix()
    vals = numpy.linalg.eigvalsh(H)
    assert (numpy.isclose(vals[0], -1.1368354639104123, atol=1.e-4))
    assert (numpy.isclose(vals[1], -0.52718972, atol=1.e-4))
    assert (numpy.isclose(vals[2], -0.52718972, atol=1.e-4))
    assert (numpy.isclose(vals[-1], 0.9871391, atol=1.e-4))


@pytest.mark.skipif(condition=not qc.has_psi4, reason="you don't have psi4")
@pytest.mark.parametrize("trafo", ["JW", "BK", "BKT"])
@pytest.mark.parametrize("backend", [tequila.simulators.simulator_api.pick_backend("random"), tequila.simulators.simulator_api.pick_backend()])
def test_ucc_psi4(trafo, backend):
    if backend == "symbolic":
        pytest.skip("skipping for symbolic simulator  ... way too slow")
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    do_test_ucc(qc_interface=qc.QuantumChemistryPsi4, parameters=parameters_qc, result=-1.1368354639104123, trafo=trafo,
                backend=backend)


@pytest.mark.skipif(condition=not qc.has_pyscf, reason="you don't have pyscf")
@pytest.mark.parametrize("trafo", ["JW", "BK"])
def test_ucc_pyscf(trafo):
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    do_test_ucc(qc_interface=qc.QuantumChemistryPySCF, parameters=parameters_qc, result=-1.1368354639104123,
                trafo=trafo)


def do_test_ucc(qc_interface, parameters, result, trafo, backend="qulacs"):
    # check examples for comments
    psi4_interface = qc_interface(parameters=parameters, transformation=trafo)

    hqc = psi4_interface.make_hamiltonian()
    amplitudes = psi4_interface.compute_ccsd_amplitudes()
    U = psi4_interface.make_uccsd_ansatz(trotter_steps=1, initial_amplitudes=amplitudes, include_reference_ansatz=True)
    variables = amplitudes.make_parameter_dictionary()
    H = psi4_interface.make_hamiltonian()
    ex = ExpectationValue(U=U, H=H)
    energy = simulate(ex, variables=variables, backend=backend)
    assert (numpy.isclose(energy, result))


@pytest.mark.skipif(condition=not qc.has_psi4, reason="you don't have psi4")
def test_mp2_psi4():
    # the number might be wrong ... its definetely not what psi4 produces
    # however, no reason to expect projected MP2 is the same as UCC with MP2 amplitudes
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    do_test_mp2(qc_interface=qc.QuantumChemistryPsi4, parameters=parameters_qc, result=-1.1344497203826904)


@pytest.mark.skipif(condition=not qc.has_pyscf, reason="you don't have pyscf")
def test_mp2_pyscf():
    # the number might be wrong ... its definetely not what psi4 produces
    # however, no reason to expect projected MP2 is the same as UCC with MP2 amplitudes
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    do_test_mp2(qc_interface=qc.QuantumChemistryPySCF, parameters=parameters_qc, result=-1.1344497203826904)


def do_test_mp2(qc_interface, parameters, result):
    # check examples for comments
    psi4_interface = qc_interface(parameters=parameters)
    hqc = psi4_interface.make_hamiltonian()

    amplitudes = psi4_interface.compute_mp2_amplitudes()
    variables = amplitudes.make_parameter_dictionary()

    U = psi4_interface.make_uccsd_ansatz(trotter_steps=1, initial_amplitudes=amplitudes,
                                         include_reference_ansatz=True)
    H = psi4_interface.make_hamiltonian()
    O = ExpectationValue(U=U, H=H)

    energy = simulate(objective=O, variables=variables)
    assert (numpy.isclose(energy, result))


@pytest.mark.skipif(condition=not qc.has_psi4, reason="you don't have psi4")
@pytest.mark.parametrize("method", ["cc2", "ccsd", "cc3"])
def test_amplitudes_psi4(method):
    results = {"mp2": -1.1279946983462537, "cc2": -1.1344484090805054, "ccsd": None, "cc3": None}
    # the number might be wrong ... its definetely not what psi4 produces
    # however, no reason to expect projected MP2 is the same as UCC with MP2 amplitudes
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="sto-3g")
    do_test_amplitudes(method=method, qc_interface=qc.QuantumChemistryPsi4, parameters=parameters_qc,
                       result=results[method])


def do_test_amplitudes(method, qc_interface, parameters, result):
    # check examples for comments
    psi4_interface = qc_interface(parameters=parameters)
    hqc = psi4_interface.make_hamiltonian()
    if result is None:
        result = psi4_interface.compute_energy(method=method)
    amplitudes = psi4_interface.compute_amplitudes(method=method)
    variables = amplitudes.make_parameter_dictionary()

    U = psi4_interface.make_uccsd_ansatz(trotter_steps=1, initial_amplitudes=amplitudes,
                                         include_reference_ansatz=True)
    H = psi4_interface.make_hamiltonian()
    O = ExpectationValue(U=U, H=H)

    energy = simulate(objective=O, variables=variables)
    assert (numpy.isclose(energy, result))


@pytest.mark.skipif(condition=not tq.chemistry.has_psi4, reason="psi4 not found")
@pytest.mark.parametrize("method", ["mp2", "mp3", "mp4", "cc2", "cc3", "ccsd", "ccsd(t)", "cisd", "cisdt"])
def test_energies_psi4(method):
    parameters_qc = qc.ParametersQC(geometry="data/h2.xyz", basis_set="6-31g")
    psi4_interface = qc.QuantumChemistryPsi4(parameters=parameters_qc)
    result = psi4_interface.compute_energy(method=method)
    assert result is not None


@pytest.mark.skipif(condition=not tq.chemistry.has_psi4, reason="psi4 not found")
def test_restart_psi4():
    h2 = tq.chemistry.Molecule(geometry="data/h2.xyz", basis_set="6-31g")
    wfn = h2.logs['hf'].wfn
    h2x = tq.chemistry.Molecule(geometry="data/h2x.xyz", basis_set="6-31g", guess_wfn=wfn)
    wfnx = h2x.logs['hf'].wfn
    with open(h2x.logs['hf'].filename, "r") as f:
        found = False
        for line in f:
            if "Reading orbitals from file 180" in line:
                found = True
                break
        assert found

    wfnx.to_file("data/test_wfn.npy")
    h2 = tq.chemistry.Molecule(geometry="data/h2.xyz", basis_set="6-31g", name="data/andreasdorn",
                               guess_wfn="data/test_wfn.npy")
    with open(h2.logs['hf'].filename, "r") as f:
        found = False
        for line in f:
            if "Reading orbitals from file 180" in line:
                found = True
                break
        assert found

@pytest.mark.skipif(condition=not tq.chemistry.has_psi4, reason="psi4 not found")
@pytest.mark.parametrize("active", [{"A1": [2, 3]}, {"B2": [0], "B1": [0]}, {"A1":[0,1,2,3]}, {"B1":[0]}])
def test_active_spaces(active):
    mol = tq.chemistry.Molecule(geometry="data/h2o.xyz", basis_set="sto-3g", active_orbitals=active)
    H = mol.make_hamiltonian()
    Uhf = mol.prepare_reference()
    hf = tequila.simulators.simulator_api.simulate(tq.ExpectationValue(U=Uhf, H=H))
    assert (tq.numpy.isclose(hf, mol.energies["hf"], atol=1.e-4))
    qubits = 2*sum([len(v) for v in active.values()])
    assert (H.n_qubits == qubits)
