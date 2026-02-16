# Strategy Selection Guide

## Decision Tree

```
Is this a numeric value?
├── Yes → Should higher win?
│   ├── Yes → MaxWins
│   └── No → MinWins
└── No → Is this a collection/set?
    ├── Yes → UnionSet (or Concat)
    └── No → Is there a natural ordering?
        ├── Yes → Priority(["low", "medium", "high"])
        └── No → Does length matter?
            ├── Yes → LongestWins
            └── No → LWW (default)
```

## Strategy Comparison

| Scenario | Strategy | Why |
|----------|----------|-----|
| User's display name | LWW | Most recent update should win |
| High score | MaxWins | We want the best score |
| Minimum price | MinWins | We want the lowest price |
| Tags/categories | UnionSet | Combine all tags |
| Status workflow | Priority | Business rules define ordering |
| Description text | LongestWins | Longer = more detailed |
| Audit notes | Concat | Preserve all notes |
| Custom business logic | Custom | Your function, your rules |

## Example: E-commerce Product

```python
schema = MergeSchema(
    default=LWW(),
    product_name=LWW(),
    price=MinWins(),             # Lowest price wins (customer-friendly)
    rating=MaxWins(),            # Highest rating
    categories=UnionSet(","),    # All categories
    description=LongestWins(),   # Most detailed description
    status=Priority(["draft", "pending", "active", "featured"]),
)
```
