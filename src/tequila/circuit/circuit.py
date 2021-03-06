from tequila.circuit._gates_impl import QGateImpl
from tequila import TequilaException
from tequila import BitNumbering
import typing, copy
from collections import defaultdict


class QCircuit():

    @property
    def moments(self):
        table = {i: 0 for i in self.qubits}
        moms = []
        moms.append(Moment())
        for g in self.gates:
            qus = g.qubits
            spots = [table[q] for q in qus]

            if max(spots) == len(moms):

                moms.append(Moment([g]))
            else:
                moms[max(spots)].add_gate(g)
            for q in qus:
                table[q] = max(spots) + 1
        for mom in moms:
            mom.sort_gates()
        return moms

    @property
    def canonical_moments(self):
        table_u = {i: 0 for i in self.qubits}
        table_p = {i: 0 for i in self.qubits}
        moms = []
        moms.append((Moment(), Moment()))

        for g in self.gates:
            p = 0
            qus = g.qubits
            if g.is_parametrized():
                if hasattr(g.parameter, 'extract_variables'):
                    p = 1

            if p == 0:
                spots = [table_u[q] for q in qus] + [table_p[q] for q in qus]
                if max(spots) == len(moms):
                    moms.append((Moment([g]), Moment()))
                else:
                    moms[max(spots)][0].add_gate(g)
                for q in qus:
                    table_u[q] = max(spots) + 1
                    table_p[q] = max(spots)

            else:
                spots = [max(table_p[q], table_u[q] - 1) for q in qus]
                if max(spots) == len(moms):
                    moms.append((Moment(), Moment([g])))
                else:
                    moms[max(spots)][1].add_gate(g)
                for q in qus:
                    table_u[q] = table_p[q] = max(spots) + 1
        noms = []
        for m in moms:
            noms.extend([m[0], m[1]])

        for nom in noms:
            nom.sort_gates()
        return noms

    @property
    def depth(self):
        return len(self.moments)

    @property
    def canonical_depth(self):
        return len(self.canonical_moments)

    @property
    def gates(self):
        if self._gates is None:
            return []
        else:
            return self._gates

    @property
    def numbering(self) -> BitNumbering:
        return BitNumbering.LSB

    @property
    def qubits(self):
        accumulate = []
        for g in self.gates:
            accumulate += list(g.qubits)
        return sorted(list(set(accumulate)))

    @property
    def n_qubits(self):
        return max(self.max_qubit() + 1, self._min_n_qubits)

    @n_qubits.setter
    def n_qubits(self, other):
        self._min_n_qubits = other
        if other < self.max_qubit() + 1:
            raise TequilaException(
                "You are trying to set n_qubits to " + str(other) + " but your circuit needs at least: " + str(
                    self.max_qubit() + 1))
        return self

    def __init__(self, gates=None, parameter_map=None):
        self._n_qubits = None
        self._min_n_qubits = 0
        if gates is None:
            self._gates = []
        else:
            self._gates = list(gates)

        if parameter_map is None:
            self._parameter_map = self.make_parameter_map()
        else:
            self._parameter_map = parameter_map

    def make_parameter_map(self) -> dict:
        """
        Returns
        -------
            ParameterMap of the circuit: A dictionary with
            keys: variables in the circuit
            values: list of all gates and their positions in the circuit
            e.g. result[Variable("a")] = [(3, Rx), (5, Ry), ...]
        """
        parameter_map = defaultdict(list)
        for idx, gate in enumerate(self.gates):
            if gate.is_parametrized():
                variables = gate.extract_variables()
                for variable in variables:
                    parameter_map[variable] += [(idx, gate)]

        return parameter_map

    def is_primitive(self):
        """
        Check if this is a single gate wrapped in this structure
        :return: True if the circuit is just a single gate
        """
        return len(self.gates) == 1

    def sort_gates(self):
        sl = []
        for m in self.moments:
            sd = {}
            for gate in m.gates:
                q = min(gate.qubits)
                sd[q] = gate
            sl.extend([sd[k] for k in sorted(sd.keys())])
        self._gates = sl

    def replace_gates(self, positions: list, circuits: list, replace: list = None):
        """
        Notes
        ----------
        Replace or insert gates at specific positions into the circuit
        at different positions (faster than multiple calls to replace_gate)

        Parameters
        ----------
        positions: list of int:
            the positions at which the gates should be added. Always refer to the positions in the original circuit
        circuits: list or QCircuit:
            the gates to add at the corresponding positions
        replace: list of bool: (Default value: None)
            Default is None which corresponds to all true
            decide if gates shall be replaces or if the new parts shall be inserted without replacement
            if replace[i] = true: gate at position [i] will be replaces by gates[i]
            if replace[i] = false: gates[i] circuit will be inserted at position [i] (beaming before gate previously at position [i])
        Returns
        -------
            new circuit with inserted gates
        """

        assert len(circuits) == len(positions)
        if replace is None:
            replace = [True] * len(circuits)
        else:
            assert len(circuits) == len(replace)

        dataset = zip(positions, circuits, replace)
        dataset = sorted(dataset, key=lambda x: x[0])

        offset = 0
        new_gatelist = self.gates
        for idx, circuit, do_replace in dataset:

            # failsafe
            if hasattr(circuit, "gates"):
                gatelist = circuit.gates
            elif isinstance(circuit, typing.Iterable):
                gatelist = circuit
            else:
                gatelist = [circuit]

            pos = idx + offset
            if do_replace:
                new_gatelist = new_gatelist[:pos] + gatelist + new_gatelist[pos + 1:]
                offset += len(gatelist) - 1
            else:
                new_gatelist = new_gatelist[:pos] + gatelist + new_gatelist[pos:]
                offset += len(gatelist)

        result = QCircuit(gates=new_gatelist)
        result.n_qubits = max(result.n_qubits, self.n_qubits)
        return result

    def insert_gates(self, positions, gates):
        """
        See replace_gates
        """
        return self.replace_gates(positions=positions, circuits=gates, replace=[False] * len(gates))

    def dagger(self):
        """
        :return: Return adjoint of the circuit
        """
        result = QCircuit()
        for g in reversed(self.gates):
            result += g.dagger()
        return result

    def extract_variables(self) -> list:
        """
        return a list containing all the variable objects contained in any of the gates within the unitary
        including those nested within transforms.
        """
        variables = []
        for i, g in enumerate(self.gates):
            if g.is_parametrized():
                variables += g.extract_variables()
        return list(set(variables))

    def max_qubit(self):
        """
        :return: Maximum index this circuit touches
        """
        qmax = 0
        for g in self.gates:
            qmax = max(qmax, g.max_qubit)
        return qmax

    def is_fully_parametrized(self):
        for gate in self.gates:
            if not gate.is_parametrized():
                return False
            else:
                if hasattr(gate, 'parameter'):
                    if not hasattr(gate.parameter, 'wrap'):
                        return False
                    else:
                        continue
                else:
                    continue
        return True

    def is_fully_unparametrized(self):
        for gate in self.gates:
            if not gate.is_parametrized():
                continue
            else:
                if hasattr(gate, 'parameter'):
                    if not hasattr(gate.parameter, 'wrap'):
                        continue
                    else:
                        return False
                else:
                    return False
        return True

    def is_mixed(self):
        return not (self.is_fully_parametrized() or self.is_fully_unparametrized())

    def __iadd__(self, other):
        # duck typing
        other = self.wrap_gate(gate=other)

        offset = len(self.gates)
        for k, v in other._parameter_map.items():
            self._parameter_map[k] += [(x[0] + offset, x[1]) for x in v]

        self._gates += other.gates
        self._min_n_qubits = max(self._min_n_qubits, other._min_n_qubits)

        return self

    def __add__(self, other):
        gates = [g.copy() for g in (self.gates + other.gates)]
        result = QCircuit(gates=gates)
        result._min_n_qubits = max(self._min_n_qubits, other._min_n_qubits)
        return result

    def __str__(self):
        result = "circuit: \n"
        for g in self.gates:
            result += str(g) + "\n"
        return result

    def __eq__(self, other):
        if len(self.gates) != len(other.gates):
            return False
        self.sort_gates()
        other.sort_gates()
        for i, g in enumerate(self.gates):
            if g != other.gates[i]:
                return False
        return True

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def wrap_gate(gate: QGateImpl):
        """
        :param gate: Abstract Gate
        :return: wrap gate in QCircuit structure (enable arithmetic operators)
        """
        if isinstance(gate, QCircuit):
            return gate
        if isinstance(gate, list):
            return QCircuit(gates=gate)
        else:
            return QCircuit(gates=[gate])

    @staticmethod
    def from_moments(moments: typing.List):
        c = QCircuit()
        for m in moments:
            c += m.as_circuit()
        return c

    def verify(self) -> bool:
        for k, v, in self._parameter_map.items():
            test = [self.gates[x[0]] == x[1] for x in v]
            test += [k in self._gates[x[0]].extract_variables() for x in v]
        return all(test)


class Moment(QCircuit):
    '''
    the class which represents all operations to be applied at once in a circuit.
    wraps a list of gates with a list of occupied qubits.
    Can be converted directly to a circuit.
    '''

    @property
    def moments(self):
        return [self]

    @property
    def canonical_moments(self):
        mu = []
        mp = []
        for gate in self.gates:
            if not gate.is_parametrized():
                mu.append(gate)
            else:
                if hasattr(gate, 'parameter'):
                    if not hasattr(gate.parameter, 'wrap'):
                        mu.append(gate)
                    else:
                        mp.append(gate)
                else:
                    mp.append(gate)
        return [Moment(mu), Moment(mp)]

    @property
    def depth(self):
        return 1

    @property
    def canonical_depth(self):
        return 2

    def __init__(self, gates: typing.List[QGateImpl] = None, sort=False):
        super().__init__(gates=gates)
        occ = []
        if gates is not None:
            for g in list(gates):
                for q in g.qubits:
                    if q in occ:
                        raise TequilaException(
                            'cannot have doubly occupied qubits, which occurred at qubit {}'.format(str(q)))
                    else:
                        occ.append(q)
        if sort:
            self.sort_gates()

    def with_gate(self, gate: typing.Union[QCircuit, QGateImpl]):
        prev = self.qubits
        newq = gate.qubits
        overlap = []
        for n in newq:
            if n in prev:
                overlap.append(n)

        gates = copy.deepcopy(self.gates)
        if len(overlap) == 0:
            gates.append(gate)
        else:
            for i, g in enumerate(gates):
                if any([q in overlap for q in g.qubits]):
                    del g
            gates.append(gate)

        return Moment(gates=gates)

    def with_gates(self, gates):
        gl = list(gates)
        first_overlap = []
        for g in gl:
            for q in g.qubits:
                if q not in first_overlap:
                    first_overlap.append(q)
                else:
                    raise TequilaException('cannot have a moment with multiple operations acting on the same qubit!')

        new = self.with_gate(gl[0])
        for g in gl[1:]:
            new = new.with_gate(g)
        new.sort_gates()
        return new

    def add_gate(self, gate: typing.Union[QCircuit, QGateImpl]):
        prev = self.qubits
        newq = gate.qubits
        for n in newq:
            if n in prev:
                raise TequilaException(
                    'cannot add gate {} to moment; qubit {} already occupied.'.format(str(gate), str(n)))

        self._gates.append(gate)
        self.sort_gates()
        return self

    def replace_gate(self, position, gates):
        if hasattr(gates, '__iter__'):
            gs = gates
        else:
            gs = [gates]

        new = self.gates[:position]
        new.extend(gs)
        new.extend(self.gates[(position + 1):])
        try:
            return Moment(gates=new)
        except:
            return QCircuit(gates=new)

    def as_circuit(self):
        return QCircuit(gates=self.gates)

    def fully_parametrized(self):
        for gate in self.gates:
            if not gate.is_parametrized():
                return False
            else:
                if hasattr(gate, 'parameter'):
                    if not hasattr(gate.parameter, 'wrap'):
                        return False
                    else:
                        continue
                else:
                    continue
        return True

    def __str__(self):
        result = "Moment: "
        for g in self.gates:
            result += str(g) + ", "
        return result

    def __iadd__(self, other):

        new = self.as_circuit()
        if isinstance(other, QGateImpl):
            other = new.wrap_gate(other)

        if isinstance(other, list) and isinstance(other[0], QGateImpl):
            new._gates += other

        if isinstance(other, list) and isinstance(other[0], QCircuit):
            for o in other:
                new._gates += o.gates
        else:
            new._gates += other.gates
        new._min_n_qubits = max(self._min_n_qubits, other._min_n_qubits)
        if new.depth == 1:
            new = Moment(new.gates)
        return new

    def __add__(self, other):
        if isinstance(other, Moment):
            gates = [g.copy() for g in (self.gates + other.gates)]
            result = QCircuit(gates=gates)
            result._min_n_qubits = max(self.as_circuit()._min_n_qubits, other._min_n_qubits)
            if result.depth == 1:
                result = Moment(gates=result.gates)
                result._min_n_qubits = max(self.as_circuit()._min_n_qubits, other._min_n_qubits)
        elif isinstance(other, QCircuit) and not isinstance(other, Moment):
            if not other.is_primitive():
                gates = [g.copy() for g in (self.gates + other.gates)]
                result = QCircuit(gates=gates)
                result._min_n_qubits = max(self.as_circuit()._min_n_qubits, other._min_n_qubits)
            else:
                try:
                    result = self.add_gate(other.gates[0])
                    result._min_n_qubits += len(other.qubits)
                except:
                    result = self.as_circuit() + QCircuit.wrap_gate(other)
                    result._min_n_qubits = max(self.as_circuit()._min_n_qubits, QCircuit.wrap_gate(other)._min_n_qubits)

        else:
            if isinstance(other, QGateImpl):
                try:
                    result = self.add_gate(other)
                    result._min_n_qubits += len(other.qubits)
                except:
                    result = self.as_circuit() + QCircuit.wrap_gate(other)
                    result._min_n_qubits = max(self.as_circuit()._min_n_qubits, QCircuit.wrap_gate(other)._min_n_qubits)
            else:
                raise TequilaException(
                    'cannot add moments to types other than QCircuit,Moment,or Gate; recieved summand of type {}'.format(
                        str(type(other))))
        return result

    @staticmethod
    def wrap_gate(gate: QGateImpl):
        """
        :param gate: Abstract Gate
        :return: wrap gate in QCircuit structure (enable arithmetic operators)
        """
        if isinstance(gate, QCircuit):
            return gate
        else:
            return Moment(gates=[gate])

    @staticmethod
    def from_moments(moments: typing.List):
        raise TequilaException(
            'this method should never be called from Moment. Call from the QCircuit class itself instead.')
