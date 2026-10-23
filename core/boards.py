"""Forum boards.

A board is a post category shown the way a forum shows sections: its own colour,
icon and one-line purpose. Keys must match Post.CATEGORY_CHOICES.
"""
from django.db.models import Count, Max

from .models import Post

BOARDS = {
    'General': {
        'slug': 'general', 'icon': 'fa-comments',
        'blurb': 'Campus life, questions and anything else.',
    },
    'Help Needed': {
        'slug': 'help', 'icon': 'fa-life-ring',
        'blurb': 'Ask seniors about courses, halls, admissions and paperwork.',
    },
    'Blood Request': {
        'slug': 'blood', 'icon': 'fa-droplet',
        'blurb': 'Urgent donor requests. Members list their blood group.',
    },
    'Job Opportunity': {
        'slug': 'jobs', 'icon': 'fa-briefcase',
        'blurb': 'Jobs, internships and referrals shared by alumni.',
    },
    'Tuition Offer': {
        'slug': 'tuition', 'icon': 'fa-chalkboard-user',
        'blurb': 'Tuition openings in Chattogram and back home.',
    },
    'Event': {
        'slug': 'event', 'icon': 'fa-calendar-day',
        'blurb': 'Meetups, programs and plans for getting together.',
    },
    'Success Story': {
        'slug': 'success', 'icon': 'fa-award',
        'blurb': 'Results, placements and milestones worth celebrating.',
    },
    'Sports': {
        'slug': 'sports', 'icon': 'fa-futbol',
        'blurb': 'Tournaments, teams and match day talk.',
    },
    'Celebrations': {
        'slug': 'celebrations', 'icon': 'fa-cake-candles',
        'blurb': 'Eid, Pohela Boishakh, farewells and reunions.',
    },
}

DEFAULT_BOARD = {'slug': 'general', 'icon': 'fa-comments', 'blurb': ''}


def board_for(category):
    return {'name': category, **BOARDS.get(category, DEFAULT_BOARD)}


def board_list():
    """Every board with its topic count and last activity, in CATEGORY_CHOICES order."""
    stats = {
        row['category']: row
        for row in Post.objects.values('category').annotate(topics=Count('id'), last=Max('created_at'))
    }
    boards = []
    for value, _label in Post.CATEGORY_CHOICES:
        row = stats.get(value, {})
        boards.append({**board_for(value), 'topics': row.get('topics', 0), 'last': row.get('last')})
    return boards
