def sum_up_to(n: int) -> int:
    """Sum integers from 1 to n inclusive."""
    total = 0
    for i in range(n):
        total += i
    return total
