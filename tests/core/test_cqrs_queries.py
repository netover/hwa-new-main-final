"""
Comprehensive test suite for CQRS query implementations.
"""

import pytest

from resync.cqrs.queries import (
    GetSystemStatusQuery,
    GetWorkstationsStatusQuery,
    GetJobsStatusQuery,
    GetCriticalPathStatusQuery,
    GetJobStatusQuery,
    GetJobStatusBatchQuery,
    GetSystemHealthQuery,
    SearchJobsQuery,
    GetPerformanceMetricsQuery,
    CheckTWSConnectionQuery,
)


class TestQueryObjects:
    """Test cases for CQRS query objects."""

    def test_get_system_status_query_creation(self):
        """Test GetSystemStatusQuery can be created."""
        query = GetSystemStatusQuery()
        assert query is not None
        assert isinstance(query, GetSystemStatusQuery)

    def test_get_workstations_status_query_creation(self):
        """Test GetWorkstationsStatusQuery can be created."""
        query = GetWorkstationsStatusQuery()
        assert query is not None
        assert isinstance(query, GetWorkstationsStatusQuery)

    def test_get_jobs_status_query_creation(self):
        """Test GetJobsStatusQuery can be created."""
        query = GetJobsStatusQuery()
        assert query is not None
        assert isinstance(query, GetJobsStatusQuery)

    def test_get_critical_path_status_query_creation(self):
        """Test GetCriticalPathStatusQuery can be created."""
        query = GetCriticalPathStatusQuery()
        assert query is not None
        assert isinstance(query, GetCriticalPathStatusQuery)

    def test_get_job_status_query_creation(self):
        """Test GetJobStatusQuery can be created with job_id."""
        job_id = "TEST_JOB_001"
        query = GetJobStatusQuery(job_id=job_id)
        assert query is not None
        assert isinstance(query, GetJobStatusQuery)
        assert query.job_id == job_id

    def test_get_job_status_batch_query_creation(self):
        """Test GetJobStatusBatchQuery can be created with job_ids."""
        job_ids = ["JOB1", "JOB2", "JOB3"]
        query = GetJobStatusBatchQuery(job_ids=job_ids)
        assert query is not None
        assert isinstance(query, GetJobStatusBatchQuery)
        assert query.job_ids == job_ids

    def test_get_job_status_batch_query_empty_list(self):
        """Test GetJobStatusBatchQuery can be created with empty job_ids."""
        job_ids = []
        query = GetJobStatusBatchQuery(job_ids=job_ids)
        assert query is not None
        assert isinstance(query, GetJobStatusBatchQuery)
        assert query.job_ids == job_ids

    def test_get_system_health_query_creation(self):
        """Test GetSystemHealthQuery can be created."""
        query = GetSystemHealthQuery()
        assert query is not None
        assert isinstance(query, GetSystemHealthQuery)

    def test_search_jobs_query_creation(self):
        """Test SearchJobsQuery can be created with search parameters."""
        search_term = "TEST"
        limit = 20
        query = SearchJobsQuery(search_term=search_term, limit=limit)
        assert query is not None
        assert isinstance(query, SearchJobsQuery)
        assert query.search_term == search_term
        assert query.limit == limit

    def test_search_jobs_query_default_limit(self):
        """Test SearchJobsQuery uses default limit when not specified."""
        search_term = "TEST"
        query = SearchJobsQuery(search_term=search_term)
        assert query is not None
        assert isinstance(query, SearchJobsQuery)
        assert query.search_term == search_term
        assert query.limit == 10  # Default limit

    def test_get_performance_metrics_query_creation(self):
        """Test GetPerformanceMetricsQuery can be created."""
        query = GetPerformanceMetricsQuery()
        assert query is not None
        assert isinstance(query, GetPerformanceMetricsQuery)

    def test_check_tws_connection_query_creation(self):
        """Test CheckTWSConnectionQuery can be created."""
        query = CheckTWSConnectionQuery()
        assert query is not None
        assert isinstance(query, CheckTWSConnectionQuery)


class TestQueryValidation:
    """Test cases for query validation."""

    def test_get_job_status_query_requires_job_id(self):
        """Test GetJobStatusQuery requires job_id parameter."""
        with pytest.raises(TypeError):
            GetJobStatusQuery()  # Should fail without job_id

    def test_get_job_status_batch_query_requires_job_ids(self):
        """Test GetJobStatusBatchQuery requires job_ids parameter."""
        with pytest.raises(TypeError):
            GetJobStatusBatchQuery()  # Should fail without job_ids

    def test_search_jobs_query_requires_search_term(self):
        """Test SearchJobsQuery requires search_term parameter."""
        with pytest.raises(TypeError):
            SearchJobsQuery()  # Should fail without search_term

    def test_search_jobs_query_with_invalid_limit(self):
        """Test SearchJobsQuery with various limit values."""
        # Test with zero limit
        query = SearchJobsQuery(search_term="test", limit=0)
        assert query.limit == 0

        # Test with negative limit
        query = SearchJobsQuery(search_term="test", limit=-1)
        assert query.limit == -1

        # Test with large limit
        query = SearchJobsQuery(search_term="test", limit=1000)
        assert query.limit == 1000


class TestQueryEquality:
    """Test cases for query equality and comparison."""

    def test_get_system_status_query_equality(self):
        """Test GetSystemStatusQuery equality."""
        query1 = GetSystemStatusQuery()
        query2 = GetSystemStatusQuery()
        assert query1 == query2

    def test_get_job_status_query_equality(self):
        """Test GetJobStatusQuery equality."""
        job_id = "TEST_JOB"
        query1 = GetJobStatusQuery(job_id=job_id)
        query2 = GetJobStatusQuery(job_id=job_id)
        query3 = GetJobStatusQuery(job_id="DIFFERENT_JOB")

        assert query1 == query2
        assert query1 != query3

    def test_get_job_status_batch_query_equality(self):
        """Test GetJobStatusBatchQuery equality."""
        job_ids = ["JOB1", "JOB2"]
        query1 = GetJobStatusBatchQuery(job_ids=job_ids)
        query2 = GetJobStatusBatchQuery(job_ids=job_ids)
        query3 = GetJobStatusBatchQuery(job_ids=["JOB3", "JOB4"])

        assert query1 == query2
        assert query1 != query3

    def test_search_jobs_query_equality(self):
        """Test SearchJobsQuery equality."""
        query1 = SearchJobsQuery(search_term="test", limit=10)
        query2 = SearchJobsQuery(search_term="test", limit=10)
        query3 = SearchJobsQuery(search_term="test", limit=20)
        query4 = SearchJobsQuery(search_term="different", limit=10)

        assert query1 == query2
        assert query1 != query3
        assert query1 != query4


class TestQuerySerialization:
    """Test cases for query serialization and representation."""

    def test_get_job_status_query_repr(self):
        """Test GetJobStatusQuery string representation."""
        job_id = "TEST_JOB_001"
        query = GetJobStatusQuery(job_id=job_id)
        repr_str = repr(query)
        assert "GetJobStatusQuery" in repr_str
        assert job_id in repr_str

    def test_search_jobs_query_repr(self):
        """Test SearchJobsQuery string representation."""
        search_term = "test_search"
        limit = 25
        query = SearchJobsQuery(search_term=search_term, limit=limit)
        repr_str = repr(query)
        assert "SearchJobsQuery" in repr_str
        assert search_term in repr_str
        assert str(limit) in repr_str

    def test_get_job_status_batch_query_repr(self):
        """Test GetJobStatusBatchQuery string representation."""
        job_ids = ["JOB1", "JOB2", "JOB3"]
        query = GetJobStatusBatchQuery(job_ids=job_ids)
        repr_str = repr(query)
        assert "GetJobStatusBatchQuery" in repr_str
        # Should contain the job_ids in some form
        for job_id in job_ids:
            assert job_id in repr_str


class TestQueryEdgeCases:
    """Test cases for query edge cases and boundary conditions."""

    def test_get_job_status_query_with_special_characters(self):
        """Test GetJobStatusQuery with special characters in job_id."""
        special_job_ids = [
            "JOB-WITH-DASHES",
            "JOB_WITH_UNDERSCORES",
            "JOB.WITH.DOTS",
            "JOB@WITH@SYMBOLS",
            "JOB WITH SPACES",
            "JOB123WITH456NUMBERS",
            "VERY_LONG_JOB_NAME_THAT_EXCEEDS_NORMAL_LENGTH_EXPECTATIONS_FOR_TESTING_PURPOSES",
        ]

        for job_id in special_job_ids:
            query = GetJobStatusQuery(job_id=job_id)
            assert query.job_id == job_id

    def test_search_jobs_query_with_special_search_terms(self):
        """Test SearchJobsQuery with special search terms."""
        special_terms = [
            "",  # Empty string
            " ",  # Space
            "test with spaces",
            "test-with-dashes",
            "test_with_underscores",
            "test.with.dots",
            "test@with@symbols",
            "123456789",  # Numbers only
            "MiXeD cAsE tErM",  # Mixed case
            "very long search term that might be used in real scenarios",
            "unicode_test_ñáéíóú",  # Unicode characters
        ]

        for term in special_terms:
            query = SearchJobsQuery(search_term=term, limit=5)
            assert query.search_term == term
            assert query.limit == 5

    def test_get_job_status_batch_query_with_many_jobs(self):
        """Test GetJobStatusBatchQuery with large number of job IDs."""
        # Test with many job IDs
        many_job_ids = [f"JOB_{i:04d}" for i in range(1000)]
        query = GetJobStatusBatchQuery(job_ids=many_job_ids)
        assert len(query.job_ids) == 1000
        assert query.job_ids[0] == "JOB_0000"
        assert query.job_ids[-1] == "JOB_0999"

    def test_get_job_status_batch_query_with_duplicate_jobs(self):
        """Test GetJobStatusBatchQuery with duplicate job IDs."""
        job_ids_with_duplicates = ["JOB1", "JOB2", "JOB1", "JOB3", "JOB2"]
        query = GetJobStatusBatchQuery(job_ids=job_ids_with_duplicates)
        assert query.job_ids == job_ids_with_duplicates  # Should preserve duplicates

    def test_search_jobs_query_with_extreme_limits(self):
        """Test SearchJobsQuery with extreme limit values."""
        # Test with very large limit
        query = SearchJobsQuery(search_term="test", limit=999999)
        assert query.limit == 999999

        # Test with zero limit
        query = SearchJobsQuery(search_term="test", limit=0)
        assert query.limit == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
