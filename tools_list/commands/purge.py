"""The purge command: check every blacklist entry without prompts or a browser.

404 removes the entry, a redirect renames it, and any other error aborts.
"""

from tools_list.blacklist import check_blacklist_entry, display_path, load_blacklist, write_blacklist
from tools_list.config import load_config
from tools_list.log import clear_progress, log_info, show_progress


def purge_blacklist(blacklist):
    """Check every blacklist entry without prompts or a browser; return the purged copy."""
    purged = dict(blacklist)
    log_info(f"Checking {len(purged)} blacklist entries...")
    urls = sorted(purged)
    for index, url in enumerate(urls, 1):
        show_progress(index, len(urls), url)
        new_url = check_blacklist_entry(url)
        clear_progress()
        if new_url is None:
            del purged[url]
            log_info(f"Repository '{url}' does no longer exist, purging...")
        elif new_url != url:
            purged[new_url] = purged.pop(url)
            log_info(f"Repository '{url}' was renamed to '{new_url}', updating...")
    return purged


def run(args):
    config = load_config(args.project)
    app_dir = config.directory
    blacklist_file = config.blacklist_path

    blacklist = load_blacklist(blacklist_file)

    if not blacklist:
        log_info("Current blacklist is empty!")
        return

    purged = purge_blacklist(blacklist)
    display = display_path(app_dir, blacklist_file)

    if purged == blacklist:
        log_info(f"No changes to {display}!")
        return

    log_info(f"Writing {len(purged)} entries to '{display}'...")
    write_blacklist(blacklist_file, purged)
    log_info(f"Updated {display}, commit the changes when ready.")
