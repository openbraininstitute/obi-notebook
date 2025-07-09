# obi-notebook

Convenience functions for OBI notebooks.

## Installation

```
pip install obi-notebook
```

## examples


select a project_context
```
from obi_notebook import get_projects
project_context = get_projects.get_projects(token)
```

select circuit ids
```
from obi_notebook import get_entities
circuit_ids = []
circuit_ids = get_entities.get_entities("circuit", token, circuit_ids)
```

## demo

Multi-selection is possible.

![demo](./demo.gif)

Copyright (c) 2025 Open Brain Institute
