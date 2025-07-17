import re
import asyncio
import humanize
from .Logger import get_logger
logger = get_logger()

def paginate_list(items: list, page: int = 0, page_size: int = 5, force_paginate: bool = False) -> tuple[list, int, int, int]:
    """
    Paginate a list of items.

    Args:
        items (list): The list of items to paginate.
        page (int): The page number (0-based).
        page_size (int): Number of items per page.
        force_paginate (bool): If True, always paginate even if items fit on one page.

    Returns:
        tuple: (items_on_page, total_pages, start_index, end_index)
            - items_on_page (list): The items for the current page.
            - total_pages (int): Total number of pages.
            - start_index (int): Start index of items on this page.
            - end_index (int): End index (exclusive) of items on this page.

    Raises:
        ValueError: If page or page_size is negative.
    """
    if page < 0 or page_size <= 0:
        raise ValueError("Page must be >= 0 and page_size must be > 0.")
    if not force_paginate and len(items) <= page_size:
        # No need to paginate, return all items in one page
        return items, 1, 0, len(items)
    total_pages = (len(items) + page_size - 1) // page_size
    if page >= total_pages:
        page = max(0, total_pages - 1)
    start = page * page_size
    end = min(start + page_size, len(items))
    return items[start:end], total_pages, start, end

def format_size(bytes_size):
    if bytes_size < 1024 ** 2:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 ** 3:
        return f"{bytes_size / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes_size / (1024 ** 3):.2f} GB"

def format_human_size(size_bytes):
    """Return a human-readable file size string using humanize."""
    return humanize.naturalsize(size_bytes, binary=True)

def get_breadcrumb(service, folder_stack, current_folder, get_folder_name_func):
    """Build a breadcrumb path from folder_stack and current_folder using get_folder_name_func."""
    path = ['root']
    for folder_id in folder_stack:
        if folder_id != 'root':
            try:
                path.append(get_folder_name_func(service, folder_id))
            except Exception as e:
                logger.error(f"Error in get_breadcrumb: failed to get folder name for {folder_id}: {e}")
                path.append('...')
    if current_folder != 'root':
        try:
            path.append(get_folder_name_func(service, current_folder))
        except Exception as e:
            logger.error(f"Error in get_breadcrumb: failed to get folder name for {current_folder}: {e}")
            path.append('...')
    return ' / '.join(path)

async def is_url(text):
    return bool(re.match(r'^https?://', text))

# Add more utilities as needed for formatting, validation, etc. 