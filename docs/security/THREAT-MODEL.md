# E4 Threat Model

## Scope

This document defines the adversary model, assumptions, and security
boundaries for the E4 Recursive Trust-Delta Protocol as implemented
in crdt-merge v0.9.5.

## System Model

E4 operates within a partially synchronous gossip network where nodes
exchange CRDT state (merge operations on model weights or data) and
trust evidence (observations about peer behaviour).

**Nodes:** Each node holds a local replica of the CRDT state and a local
view of the trust lattice. Nodes communicate via pairwise gossip with
no central coordinator.

**Identifiers:** Each node has a stable peer identifier. The current
implementation uses string identifiers. Cryptographic identity binding
(Ed25519 keypairs) is defined via the `SignatureScheme` interface but
ships with HMAC-SHA256 as the concrete backend.

## Adversary Model

E4 defends against the following adversarial behaviours:

### Equivocation (Double-Reporting)
An adversary sends conflicting state to different peers. E4 detects
equivocation through Merkle root divergence: if a peer claims state S
to node A and state S' to node B, honest nodes that gossip will observe
incompatible Merkle roots for that peer's contributions. The trust
lattice records equivocation evidence and reduces the offending peer's
trust score below the gating threshold.

### Contribution Poisoning
An adversary submits deliberately corrupted data (e.g., poisoned model
weights designed to degrade collective performance). E4's gating layer
filters contributions from peers whose trust score falls below a
configurable threshold. The trust score incorporates contribution
quality observations from honest peers.

### Sybil Amplification
An adversary creates multiple identities to amplify influence. E4's
resilience subpackage includes long-con sybil detection that tracks
peer contribution patterns over time. Sybil clusters exhibit correlated
behaviour (simultaneous joins, identical contribution patterns, trust
score inflation) that the `long_con_sybil.py` module flags.

### Selective Withholding
An adversary participates honestly most of the time but withholds
specific critical updates. E4's causal trust clock tracks monotonic
logical time per peer. Gaps in the causal sequence are observable
and feed into trust score computation.

### Partition Exploitation
An adversary exploits network partitions to present different state to
isolated groups. E4's partition reconciliation module detects state
divergence after partition healing and flags peers whose contribution
history is inconsistent across partition boundaries.

## What E4 Does NOT Defend Against

**Compromised majority.** If more than half the peers are adversarial
and coordinate perfectly, E4 cannot distinguish honest from malicious
contributions. This is the standard honest-majority assumption shared
by all Byzantine fault-tolerant systems without cryptographic proofs
of work or stake.

**Side-channel attacks.** E4 operates at the application layer. It does
not defend against network-level attacks (traffic analysis, DNS
hijacking, TLS downgrade) or hardware side channels.

**Key compromise.** If an adversary obtains a peer's signing key (when
cryptographic identity is enabled), E4 cannot distinguish the
adversary from the legitimate peer. Key rotation and revocation are
outside E4's scope.

**Denial of service.** E4 can exclude misbehaving peers from the trust
lattice but cannot prevent an adversary from flooding the network with
messages. Rate limiting is a transport-layer concern.

**Model quality beyond detection.** E4 detects and excludes
contributions from low-trust peers. It does not independently verify
that high-trust contributions improve model quality. Quality
evaluation (accuracy on held-out data) is a separate concern handled
by the application layer.

## Assumptions

1. **Honest majority.** At least 51% of participating peers are honest
   and follow the protocol. E4's exclusion mechanism converges when
   honest nodes share evidence about adversarial behaviour.

2. **Reliable gossip (eventually).** Messages between honest peers are
   delivered within a bounded (but potentially large) delay. E4 does
   not assume synchronous delivery.

3. **Authenticated channels.** When the cryptographic backend is
   active, peers authenticate messages. With the default HMAC-SHA256
   backend, authentication requires a shared secret between peers.

4. **Stable identifiers.** Each peer's identifier persists across
   sessions. E4's trust history is meaningless if identifiers are
   ephemeral.

## SLT vs Classical BFT

E4 implements Symbiotic Lattice Trust (SLT), not classical Byzantine
Fault Tolerance (BFT).

**Classical BFT** (PBFT, Tendermint, HotStuff) achieves consensus: all
honest nodes agree on a single total order of operations. This requires
coordinated voting rounds and typically tolerates f < n/3 failures.

**SLT** achieves convergent exclusion: honest nodes independently
converge on the same trust state and therefore the same filtered view
of contributions. There is no voting round, no leader election, and no
total ordering. SLT tolerates f < n/2 failures because exclusion
requires only that honest nodes outnumber adversarial ones, not that
they reach agreement within a fixed round.

The trade-off: SLT provides weaker guarantees than classical BFT
(no total order, no finality within a round) but operates without
coordination overhead and composes naturally with CRDT semantics
(which also do not require total ordering).

## Trust Score Computation

Trust scores are computed as a product lattice across four dimensions:

- **Integrity:** Merkle root consistency, equivocation detection
- **Availability:** Causal clock gap analysis, participation rate
- **Quality:** Contribution impact observations from peers
- **History:** Long-term behaviour pattern (weighted towards recent)

Each dimension produces a score in [0.0, 1.0]. The overall trust score
is the geometric mean of all four dimensions. A peer is excluded from
merge operations when their overall trust score falls below the
configurable gating threshold (default: 0.3).

## Performance Characteristics

Trust evidence entries are small (typically < 1 KB each). The overhead
of E4 on merge operations is bounded by the number of peers in the
trust lattice, not the size of the data being merged.

Internal benchmarks show 9.69ms federation latency with 100 peers and
injected Byzantine actors. These numbers were measured on the
development hardware described in the benchmark notebook and have not
been independently reproduced.

## Cryptographic Primitives

| Primitive | Interface | Default Backend | Status |
|-----------|-----------|-----------------|--------|
| Message signing | `SignatureScheme` | HMAC-SHA256 | Production |
| Identity binding | `SignatureScheme` | HMAC-SHA256 | Production |
| Ed25519 signatures | `SignatureScheme` | Ed25519 adapter | Defined, not hardened |
| Post-quantum (Dilithium) | `SignatureScheme` | PQ adapter | Defined, not hardened |
| Merkle hashing | SHA-256 | hashlib | Production |
| Content fingerprinting | MD5 | hashlib | Non-security use only |

See `docs/security/CRYPTOGRAPHY.md` for detailed cryptographic
architecture and upgrade path.
