# `crdt_merge/model/targets/hf.py`

> HuggingFace Hub source and target adapters for merge pipelines.

**Source:** `crdt_merge/model/targets/hf.py` | **Lines:** 210

---

## Constants

- `_HF_INSTALL_MSG` = `'huggingface_hub is required for HuggingFace Hub integration. Install it with: pip install huggingfa`

## Classes

### `class HfSource`

Load model weights from HuggingFace Hub for use in merge pipelines.

    Parameters
    ----------
    repo_id : str
        HuggingFace repo ID (e.g., ``"user/model-name"``).
    revision : str, optional
        Git revision (branch, tag, or commit hash).
    token : str, optional
        HuggingFace API token. If None, uses HF_TOKEN env var or cached login.


**Methods:**

#### `HfSource.__init__(self, repo_id: str, revision: Optional[str] = None, token: Optional[str] = None)`

*No docstring*

#### `HfSource._hub_api(self)`

Return a HfApi instance. Isolated for easy mocking in tests.

#### `HfSource.load(self) → dict`

Download and load model weights from HuggingFace Hub.

        Returns
        -------
        dict
            Model state dictionary.

        Raises
        ------
        FileNotFoundError
            If no loadable weight files are found.
        ImportError
            If huggingface_hub is not installed.


### `class HfTarget`

Push merged model weights to HuggingFace Hub.

    Parameters
    ----------
    repo_id : str
        Target HuggingFace repo ID.
    token : str, optional
        HuggingFace API token. If None, uses HF_TOKEN env var or cached login.
    private : bool
        Whether the repository should be private (default: False).


**Methods:**

#### `HfTarget.__init__(self, repo_id: str, token: Optional[str] = None, private: bool = False)`

*No docstring*

#### `HfTarget._hub_api(self)`

Return a HfApi instance. Isolated for easy mocking in tests.

#### `HfTarget.save(self, state_dict: dict, model_card: Optional[str] = None, commit_message: Optional[str] = None) → str`

Upload model weights to HuggingFace Hub.

        Parameters
        ----------
        state_dict : dict
            Model state dictionary to upload.
        model_card : str, optional
            Model card markdown to include as README.md.
        commit_message : str, optional
            Commit message for the upload.

        Returns
        -------
        str
            URL of the created/updated repository.


## Functions

### `_require_hf_hub()`

Lazy-import huggingface_hub, raising a clear error if missing.


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 3
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 88.9%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
