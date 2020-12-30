import re
from functools import lru_cache

from octue.exceptions import InvalidTagException
from octue.mixins import Filteree
from octue.resources.filter_containers import FilterSet


TAG_PATTERN = re.compile(r"^$|^[a-z0-9][a-z0-9:\-]*(?<![:-])$")


class Tag(Filteree):
    """ A tag starts and ends with a character in [a-z] or [0-9]. It can contain the colon discriminator or hyphens.
    Empty strings are also valid. More valid examples:
       system:32
       angry-marmaduke
       mega-man:torso:component:12
    """

    _FILTERABLE_ATTRIBUTES = ("name",)

    def __init__(self, name):
        self._name = self._clean(name)

    @property
    def name(self):
        return self._name

    @property
    @lru_cache(maxsize=1)
    def subtags(self):
        """ Return the subtags of the tag as a new TagGroup (e.g. TagGroup({'a', 'b', 'c'}) for the Tag('a:b:c'). """
        return TagGroup({Tag(subtag_name) for subtag_name in (self.name.split(":"))})

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == Tag(other).name
        elif isinstance(other, Tag):
            return self.name == other.name
        return False

    def __lt__(self, other):
        if isinstance(other, str):
            return self.name < Tag(other).name
        elif isinstance(other, Tag):
            return self.name < other.name
        return False

    def __gt__(self, other):
        if isinstance(other, str):
            return self.name > Tag(other).name
        elif isinstance(other, Tag):
            return self.name > other.name
        return False

    def __hash__(self):
        return hash(f"{type(self).__name__}{self.name}")

    def __contains__(self, item):
        return item in self.name

    def __repr__(self):
        return repr(self.name)

    def starts_with(self, value):
        """ Does the tag start with the given value? """
        return self.name.startswith(value)

    def ends_with(self, value):
        """ Does the tag end with the given value? """
        return self.name.endswith(value)

    @staticmethod
    def _clean(name):
        """ Ensure the tag name is a string and conforms to the tag regex pattern. """
        if not isinstance(name, str):
            raise InvalidTagException("Tags must be expressed as a string")

        cleaned_name = name.strip()

        if not re.match(TAG_PATTERN, cleaned_name):
            raise InvalidTagException(
                f"Invalid tag '{cleaned_name}'. Tags must contain only characters 'a-z', '0-9', ':' and '-'. They must "
                f"not start with '-' or ':'."
            )

        return cleaned_name


class TagGroup:
    """ Class to handle a group of tags as a string. """

    _FILTERSET_ATTRIBUTE = "tags"

    def __init__(self, tags=None, *args, **kwargs):
        """ Construct a TagGroup. """
        # TODO Call the superclass with *args anad **kwargs, then update everything to using ResourceBase
        tags = tags or FilterSet()

        # Space delimited string of tag names.
        if isinstance(tags, str):
            self.tags = FilterSet(Tag(tag) for tag in tags.strip().split())

        elif isinstance(tags, TagGroup):
            self.tags = FilterSet(tags.tags)

        # Tags can be some other iterable than a list, but each tag must be a Tag or string.
        elif hasattr(tags, "__iter__"):
            self.tags = FilterSet(tag if isinstance(tag, Tag) else Tag(tag) for tag in tags)

        else:
            raise InvalidTagException(
                "Tags must be expressed as a whitespace-delimited string or an iterable of strings or Tag instances."
            )

    def __str__(self):
        """ Serialise tags to a sorted list string. """
        return self.serialise()

    def __eq__(self, other):
        """ Does this TagGroup have the same tags as another TagGroup? """
        if not isinstance(other, TagGroup):
            return False
        return self.tags == other.tags

    def __iter__(self):
        """ Iterate over the tags in the TagGroup. """
        yield from self.tags

    def __len__(self):
        return len(self.tags)

    def __repr__(self):
        return f"<TagGroup({self.tags})>"

    def add_tags(self, *args):
        """ Adds one or more new tag strings to the object tags. New tags will be cleaned and validated.
        """
        self.tags |= {Tag(arg) for arg in args}

    def has_tag(self, tag):
        """ Returns true if any of the tags exactly matches value, allowing test like `if 'a' in TagGroup('a b')`
        """
        return tag in self.tags or Tag(tag) in self.tags

    def get_subtags(self):
        """ Return a new TagGroup instance with all the subtags. """
        return TagGroup(subtag for tag in self for subtag in tag.subtags)

    def starts_with(self, value):
        """ Implement a startswith method that returns true if any of the tags starts with value """
        return any(tag.starts_with(value) for tag in self.tags)

    def ends_with(self, value):
        """ Implement an endswith method that returns true if any of the tags endswith value. """
        return any(tag.ends_with(value) for tag in self.tags)

    def any_tag_contains(self, value):
        """ Implement a contains method that returns true if any of the tags contains value. """
        return any(value in tag for tag in self.tags)

    def serialise(self):
        """ Serialise tags to a sorted list string. """
        return str(sorted(self))
