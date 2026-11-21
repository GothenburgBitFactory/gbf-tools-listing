"""Tool sources: one module per provider, plus the manual includes."""

from tools_list.sources.base import Source as Source
from tools_list.sources.base import filter_tools as filter_tools
from tools_list.sources.github import GithubSource
from tools_list.sources.manual import ManualSource

SOURCES = (GithubSource(), ManualSource())
