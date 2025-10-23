# type: ignore
from flask import Flask
from routes.main import app

if __name__ == '__main__':
    app.run(debug=True)

