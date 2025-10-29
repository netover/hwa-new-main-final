#!/usr/bin/env python3

pwd = "password123!"
print(f"Senha: {pwd}")
print(f"Tem minuscula: {any(c.islower() for c in pwd)}")
print(f"Tem maiuscula: {any(c.isupper() for c in pwd)}")
print(f"Tem digito: {any(c.isdigit() for c in pwd)}")
print(f"Tem caractere especial: {any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in pwd)}")

# Verificar se 'password123' está na lista de senhas fracas
weak_passwords = {
    "password",
    "123456",
    "12345678",
    "qwerty",
    "abc123",
    "password123",
    "admin",
    "root",
    "guest",
    "test",
}

print(f"'password123' esta na lista: {'password123' in weak_passwords}")
print(f"Senha em minusculo: {pwd.lower()}")
print(f"Senha em minusculo esta na lista: {pwd.lower() in weak_passwords}")
