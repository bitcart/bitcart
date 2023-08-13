# Coding guidelines for python code

Those guidelines apply to all python code across Bitcart repositories, and to all further opened pull requests.
Your pull request might be rejected if it doesn't follow coding guidelines.

## Formatting

Each python file is run through multiple formatters to make it readable and not affect coding performance.
First of all, [isort](https://pypi.org/project/isort) is run to sort imports.
After that code is formatted with [black](https://pypi.org/project/black) formatter.
You can configure your editor to apply those formatters on save automatically.

## Linting

Our python files are linted through flake8.
Make sure to fix linting issues or disable linting when appropriate.

## General coding recommendations

Make sure to try to follow general style in the repositories. When there are many different styles in one file, it is difficult to read and maintain.

For imports, in most cases prefer the long form to maintain readability:

```python
import functools
functools.partial(...)
```

Over the short form:

```python
from functools import partial
partial(...)
```

If it is too long to use full names, use `as` construct with appropriate naming:

```python
from sqlalchemy.sql import select as sql_select
```

For imports (except for the base daemon) in the Merchants API code, we prefer using absolute over relative imports, so instead of:

```python
from .. import models
```

Use

```python
from api import models
```

Also we use `snake_case` style, which is following PEP8.

# Coding guidelines for vue/javascript code

Those guidelines apply to all vue or javascript code across Bitcart repositories, and to all further opened pull requests.
Your pull request might be rejected if it doesn't follow coding guidelines.

## Formatting

Each vue/javascript file is run through eslint with prettier to make it readable and not affect coding performance.

We don't use semicolons in our code. If using vs code prettier extension, please disable semicolons in prettier settings.

You can configure your editor to apply eslint fixes on save automatically.

## Linting

Each vue/javascript file is being linted with eslint. It identifies common issues, plus the prettier plugin identifies formatting issues.
Make sure to fix linting issues or disable linting when appropriate.

## General coding recommendations

Make sure to try to follow general style in the repositories. When there are many different styles in one file, it is difficult to read and maintain.

For naming, we try to use `camelCase` in most of our code.
