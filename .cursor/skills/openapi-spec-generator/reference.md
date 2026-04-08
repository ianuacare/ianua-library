# OpenAPI Reference (Python/Flask)

## Python to OpenAPI Type Mapping

| Python | OpenAPI type | format |
|---|---|---|
| `str` | `string` | — |
| `int` | `integer` | `int64` |
| `float` | `number` | `float` |
| `bool` | `boolean` | — |
| `datetime` | `string` | `date-time` |
| `date` | `string` | `date` |
| `dict` | `object` | — |
| `list[T]` | `array` | `items` |

## Error schema baseline
- `code`: machine-readable code
- `message`: human-readable message
- `details`: optional validation/domain details

## Endpoint checklist
- Request validation documented
- Auth requirements documented
- All response examples up to date
