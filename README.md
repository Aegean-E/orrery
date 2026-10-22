# orrery

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: <FILL: each runtime this project needs and its minimum version>
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover -s tests -t .
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status orrery` |
| Phase 4: every gate | `python aikit.py check orrery` |
| Repair memory and map, then check | `python aikit.py fix orrery` |
| Resume an interrupted task | `python aikit.py resume orrery` |

## 📦 What's Inside

```text
orrery/
├── .gitignore                <- transient AIKit state excluded
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```
