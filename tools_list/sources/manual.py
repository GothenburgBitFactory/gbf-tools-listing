"""Manual source: includes hand-curated entries verbatim."""

from tools_list.log import log_info
from tools_list.sources.base import filter_tools


class ManualSource:
    name = "manual"

    def collect(self, config, blacklist, includes):
        entries = includes.get("manual", [])
        log_info("Adding {} manual includes ...", len(entries))
        return filter_tools(entries, blacklist)
