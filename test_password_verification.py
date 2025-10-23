import asyncio
from resync.api.validation.enhanced_security import EnhancedSecurityValidator


async def test_password_verification():
    """Test password hashing and verification."""
    validator = EnhancedSecurityValidator()

    # Test with a sample password
    password = "SecurePass123!"

    # Hash the password
    hashed = await validator.hash_password(password)
    print(f"Hashed password: {hashed}")

    # Verify correct password
    result = await validator.verify_password(password, hashed)
    print(f"Verification result (correct password): {result}")

    # Verify incorrect password
    result_wrong = await validator.verify_password("WrongPassword123!", hashed)
    print(f"Verification result (wrong password): {result_wrong}")

    # Test with plain text fallback (simulating development environment)
    plain_text_hash = "$plaintext_warning$MyPlainPassword123"
    result_plain = await validator.verify_password(
        "MyPlainPassword123", plain_text_hash
    )
    print(f"Verification result (plain text): {result_plain}")

    return result and not result_wrong and result_plain


if __name__ == "__main__":
    result = asyncio.run(test_password_verification())
    print(f"All tests passed: {result}")
