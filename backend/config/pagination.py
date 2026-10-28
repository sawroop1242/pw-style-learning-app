"""Pagination used by every list endpoint.

DRF's stock ``PageNumberPagination`` fixes the page size and ignores the
``page_size`` query parameter. Every screen in this project asks for the number
of rows it can show — four lessons on the home rail, nine batches in the
catalogue grid, the whole paper list on the tests page — so without this class
each request silently came back with the default 50 rows and the rails rendered
everything the database held.

``max_page_size`` keeps a client from asking for an unbounded page.
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
