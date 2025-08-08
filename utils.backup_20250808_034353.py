def greet():
    try:
        x = 5 / 1
        print("Hello, World!")
    except ZeroDivisionError:
        print("Error: Division by zero!")