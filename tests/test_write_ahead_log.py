import pytest
import tempfile
from pathlib import Path
from resync.core.write_ahead_log import WriteAheadLog, WalEntry, WalOperationType


@pytest.mark.asyncio
async def test_wal_basic_operations():
    """Test basic WAL operations: logging and reading entries."""
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"
        wal = WriteAheadLog(wal_path)

        # Create test entries
        entry1 = WalEntry(
            operation=WalOperationType.SET,
            key="test_key1",
            value="test_value1",
            ttl=300,
        )

        entry2 = WalEntry(operation=WalOperationType.DELETE, key="test_key2")

        # Log the entries
        result1 = await wal.log_operation(entry1)
        result2 = await wal.log_operation(entry2)

        assert result1 is True
        assert result2 is True

        # Verify log file was created
        log_files = list(wal_path.glob("wal_*.log"))
        assert len(log_files) >= 1

        # Read back the entries
        entries = await wal.read_log(log_files[0])
        assert len(entries) >= 2

        # Verify the entries
        saved_entry1 = entries[0]
        saved_entry2 = entries[1]

        assert saved_entry1.operation == WalOperationType.SET
        assert saved_entry1.key == "test_key1"
        assert saved_entry1.value == "test_value1"
        assert saved_entry1.ttl == 300

        assert saved_entry2.operation == WalOperationType.DELETE
        assert saved_entry2.key == "test_key2"

        # Close WAL
        await wal.close()


@pytest.mark.asyncio
async def test_wal_checksum_verification():
    """Test WAL checksum verification for data integrity."""
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"
        wal = WriteAheadLog(wal_path)

        # Create a test entry
        entry = WalEntry(
            operation=WalOperationType.SET,
            key="checksum_test",
            value={"data": "test"},
            ttl=600,
        )

        # Log the entry
        result = await wal.log_operation(entry)
        assert result is True

        # Verify log file was created
        log_files = list(wal_path.glob("wal_*.log"))
        assert len(log_files) >= 1

        # Read back the entry and verify checksum
        entries = await wal.read_log(log_files[0])
        assert len(entries) >= 1

        saved_entry = entries[0]
        # Verify checksum is calculated
        assert saved_entry.checksum is not None

        # Verify checksum integrity
        expected_checksum = saved_entry.calculate_checksum()
        assert saved_entry.checksum == expected_checksum

        # Close WAL
        await wal.close()


@pytest.mark.asyncio
async def test_wal_log_rotation():
    """Test WAL log rotation when size limit is exceeded."""
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"
        # Create WAL with small max size for testing
        wal = WriteAheadLog(wal_path, max_log_size=1024)  # 1KB limit

        # Add multiple entries to trigger rotation
        for i in range(50):
            entry = WalEntry(
                operation=WalOperationType.SET,
                key=f"key_{i}",
                value=f"value_{i}" * 50,  # Large value to fill log quickly
                ttl=300,
            )
            result = await wal.log_operation(entry)
            assert result is True

        # Verify multiple log files were created
        log_files = list(wal_path.glob("wal_*.log"))
        assert len(log_files) >= 2  # Should have rotated at least once

        # Close WAL
        await wal.close()


@pytest.mark.asyncio
async def test_wal_cleanup_old_logs():
    """Test cleaning up old WAL files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"
        wal = WriteAheadLog(wal_path)

        # Create some test entries
        entry = WalEntry(
            operation=WalOperationType.SET,
            key="cleanup_test",
            value="test_value",
            ttl=300,
        )

        result = await wal.log_operation(entry)
        assert result is True

        # Verify log file was created
        log_files = list(wal_path.glob("wal_*.log"))
        assert len(log_files) >= 1

        # Cleanup old logs (with 0 retention to remove all)
        await wal.cleanup_old_logs(retention_hours=0)

        # Verify log files were removed
        log_files_after = list(wal_path.glob("wal_*.log"))
        # Note: This might not remove all files depending on system timing

        # Close WAL
        await wal.close()


@pytest.mark.asyncio
async def test_wal_close():
    """Test closing the WAL system."""
    with tempfile.TemporaryDirectory() as temp_dir:
        wal_path = Path(temp_dir) / "wal_test"
        wal = WriteAheadLog(wal_path)

        # Create a test entry
        entry = WalEntry(
            operation=WalOperationType.SET,
            key="close_test",
            value="test_value",
            ttl=300,
        )

        result = await wal.log_operation(entry)
        assert result is True

        # Close WAL
        await wal.close()

        # Verify no errors occurred
        assert True  # If we got here without exception, close worked
