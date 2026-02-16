# Why CRDTs for Merging?

## The Problem

When two replicas of the same data diverge, you need to merge them. Traditional approaches have problems:

| Approach | Problem |
|----------|---------|
| Last-write-wins (global) | Data loss — newer writes may overwrite important old values |
| Manual conflict resolution | Doesn't scale; requires human intervention |
| Operational transforms | Complex; order-dependent; hard to implement correctly |
| Consensus (Paxos/Raft) | Requires coordination; not available offline |

## The CRDT Solution

CRDTs provide **automatic, correct, coordination-free merging**:

1. **No data loss**: Strategies like MaxWins, UnionSet, and Priority preserve important values
2. **No manual resolution**: Every conflict has a deterministic resolution
3. **No coordination needed**: Merges happen locally without network communication
4. **Order independent**: `merge(A, B) == merge(B, A)` — works with any message ordering
5. **Offline capable**: Replicas can diverge arbitrarily and still converge on merge

## When CRDTs Are The Right Choice

- Distributed databases with eventual consistency
- Offline-first applications
- Multi-master replication
- Edge computing and IoT
- ML model merging across training runs
- Multi-agent AI systems
