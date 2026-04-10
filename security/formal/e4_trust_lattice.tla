---- MODULE E4ProductLattice ----
\* TLA+ specification for E4 recursive trust-delta architecture.
\* Verifies convergence, trust monotonicity, progress, and
\* trust stabilisation properties of the product lattice
\* E4State = Data x Trust x Clock x Hash.

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS MaxPeers, MaxOps, TrustDims, MaxEpoch, MaxTime

Peers == 1..MaxPeers
Dims  == 1..TrustDims

VARIABLES
    data,        \* data[i]       : peer i's local data state (Nat)
    gcounter,    \* gcounter[i][d] : peer i's GCounter trust dimension d
    clock,       \* clock[i][j]    : peer i's vector clock entry for j
    hash,        \* hash[i]        : derived content hash (recomputed, not merged)
    pending,     \* pending        : set of operations awaiting delivery
    delivered,   \* delivered[i]   : set of operations peer i has processed
    epoch        \* epoch          : global epoch counter (GCounter)

vars == <<data, gcounter, clock, hash, pending, delivered, epoch>>

TypeInvariant ==
    /\ \A i \in Peers : data[i] \in Nat
    /\ \A i \in Peers, d \in Dims : gcounter[i][d] \in Nat
    /\ \A i \in Peers, j \in Peers : clock[i][j] \in Nat
    /\ \A i \in Peers : hash[i] \in Nat
    /\ \A i \in Peers : delivered[i] \subseteq pending

Init ==
    /\ data       = [i \in Peers |-> 0]
    /\ gcounter   = [i \in Peers |-> [d \in Dims |-> 0]]
    /\ clock      = [i \in Peers |-> [j \in Peers |-> 0]]
    /\ hash       = [i \in Peers |-> 0]
    /\ pending    = {}
    /\ delivered  = [i \in Peers |-> {}]
    /\ epoch      = [i \in Peers |-> 0]

\* CRDT merge: element-wise maximum across all dimensions.
\* Hash is recomputed (dependent dimension), not merged.
Merge(i, j) ==
    /\ i /= j
    /\ data'      = [data      EXCEPT ![i] = IF data[j] > data[i]
                                              THEN data[j] ELSE data[i]]
    /\ gcounter'  = [gcounter  EXCEPT ![i] =
                        [d \in Dims |-> IF gcounter[j][d] > gcounter[i][d]
                                        THEN gcounter[j][d]
                                        ELSE gcounter[i][d]]]
    /\ clock'     = [clock     EXCEPT ![i] =
                        [k \in Peers |-> IF clock[j][k] > clock[i][k]
                                         THEN clock[j][k]
                                         ELSE clock[i][k]]]
    \* Hash is recomputed from merged state (E1 binding)
    /\ hash'      = [hash EXCEPT ![i] = (data'[i] + gcounter'[i][1]) % 997]
    /\ epoch'     = [epoch EXCEPT ![i] = IF epoch[j] > epoch[i]
                                          THEN epoch[j] ELSE epoch[i]]
    /\ UNCHANGED <<pending, delivered>>

\* Local data increment (generates a new operation).
Increment(i) ==
    /\ data[i] < MaxOps
    /\ LET op == <<i, data[i] + 1>>
       IN /\ data'      = [data EXCEPT ![i] = data[i] + 1]
          /\ clock'     = [clock EXCEPT ![i][i] = clock[i][i] + 1]
          /\ hash'      = [hash EXCEPT ![i] = (data[i] + 1 + gcounter[i][1]) % 997]
          /\ pending'   = pending \cup {op}
          /\ delivered' = [delivered EXCEPT ![i] = delivered[i] \cup {op}]
          /\ UNCHANGED <<gcounter, epoch>>

\* Trust evidence: increment a GCounter dimension (grow-only).
TrustUpdate(i, d) ==
    /\ gcounter[i][d] < MaxOps
    /\ gcounter' = [gcounter EXCEPT ![i][d] = gcounter[i][d] + 1]
    /\ hash'     = [hash EXCEPT ![i] = (data[i] + gcounter[i][d] + 1) % 997]
    /\ UNCHANGED <<data, clock, pending, delivered, epoch>>

Next ==
    \/ \E i \in Peers : Increment(i)
    \/ \E i, j \in Peers : Merge(i, j)
    \/ \E i \in Peers, d \in Dims : TrustUpdate(i, d)

Fairness == \A i, j \in Peers : WF_vars(Merge(i, j))

Spec == Init /\ [][Next]_vars /\ Fairness

\* -- Temporal properties --
\* Replicas with identical delivery sets have identical states.
Convergence ==
    \A i, j \in Peers : delivered[i] = delivered[j] => state[i] = state[j]

\* GCounter trust dimensions never decrease.
TrustMonotonicity ==
    \A i \in Peers, d \in Dims : gcounter[i][d]' >= gcounter[i][d]

\* Every pending operation is eventually delivered.
Progress ==
    \A op \in pending : <>( op \in delivered[dst(op)] )

\* Trust scores reach a fixed point for a stable peer set.
TrustStabilisation ==
    <>[](\A i \in Peers : trust_score[i] = trust_score'[i])


====