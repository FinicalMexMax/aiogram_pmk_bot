from datetime import datetime

data = [
    {'name': 'user', 'date': datetime(2025, 3, 15)},
    {'name': 'john', 'date': datetime(2025, 3, 16)},
    {'name': 'alex', 'date': datetime(2025, 3, 17)}
]

data = {
    datetime(2025, 3, 15): {'name': 'user'},
    datetime(2025, 3, 16): {'name': 'john'},
    datetime(2025, 3, 17): {'name': 'alex'}
}