from tests.base import BaseTestCase

from octue.resources.filter_containers import FilterSet
from octue.resources.tag import Tag, TagGroup


class TestTag(BaseTestCase):
    def test_subtags(self):
        """ Test that subtags are correctly parsed from tags. """
        self.assertEqual(Tag("a:b:c").subtags, TagGroup({Tag("a"), Tag("b"), Tag("c")}))

    def test_tag_comparison(self):
        """ Test that tags can be alphabetically compared. """
        self.assertTrue(Tag("a") < Tag("b"))
        self.assertTrue(Tag("b") > Tag("a"))
        self.assertTrue(Tag("a") != Tag("b"))
        self.assertTrue(Tag("a") == Tag("a"))

    def test_tag_comparison_with_strings(self):
        """ Test that tags can be alphabetically compared with strings in both directions. """
        self.assertTrue(Tag("a") < "b")
        self.assertTrue(Tag("b") > "a")
        self.assertTrue(Tag("a") != "b")
        self.assertTrue(Tag("a") == "a")
        self.assertTrue("b" > Tag("a"))
        self.assertTrue("a" < Tag("b"))
        self.assertTrue("b" != Tag("a"))
        self.assertTrue("a" == Tag("a"))

    def test_tags_compare_unequal_to_non_str_or_tag_types(self):
        """ Test that comparing for equality a Tag with a non-string-or-Tag type returns False. """
        self.assertFalse(Tag("a") == 1)
        self.assertTrue(Tag("a") != 1)

    def test_contains(self):
        """ Test that tags can be checked for containment. """
        self.assertIn("e", Tag("hello"))

    def test_starts_with(self):
        """ Test that the start of a tag can be checked. """
        self.assertTrue(Tag("hello").starts_with("h"))
        self.assertFalse(Tag("hello").starts_with("e"))

    def test_subtags_starts_with(self):
        """ Test that the start of subtags can be checked. """
        self.assertTrue(Tag("hello:world").subtags.starts_with("w"))
        self.assertFalse(Tag("hello:world").subtags.starts_with("e"))

    def test_ends_with(self):
        """ Test that the end of a tag can be checked. """
        self.assertTrue(Tag("hello").ends_with("o"))
        self.assertFalse(Tag("hello").ends_with("e"))

    def test_subtags_ends_with(self):
        """ Test that the end of subtags can be checked. """
        self.assertTrue(Tag("hello:world").subtags.ends_with("o"))
        self.assertFalse(Tag("hello:world").subtags.ends_with("e"))


class TestTagGroup(BaseTestCase):
    TAG_GROUP = TagGroup(tags="a b:c d:e:f")

    def test_instantiation_from_space_delimited_string(self):
        """ Test that a TagGroup can be instantiated from a space-delimited string of tag names."""
        tag_group = TagGroup(tags="a b:c d:e:f")
        self.assertEqual(tag_group.tags, FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))

    def test_instantiation_from_iterable_of_strings(self):
        """ Test that a TagGroup can be instantiated from an iterable of strings."""
        tag_group = TagGroup(tags=["a", "b:c", "d:e:f"])
        self.assertEqual(tag_group.tags, FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))

    def test_instantiation_from_iterable_of_tags(self):
        """ Test that a TagGroup can be instantiated from an iterable of Tags."""
        tag_group = TagGroup(tags=[Tag("a"), Tag("b:c"), Tag("d:e:f")])
        self.assertEqual(tag_group.tags, FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))

    def test_instantiation_from_filter_set_of_strings(self):
        """ Test that a TagGroup can be instantiated from a FilterSet of strings."""
        tag_group = TagGroup(tags=FilterSet({"a", "b:c", "d:e:f"}))
        self.assertEqual(tag_group.tags, FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))

    def test_instantiation_from_filter_set_of_tags(self):
        """ Test that a TagGroup can be instantiated from a FilterSet of Tags."""
        tag_group = TagGroup(tags=FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))
        self.assertEqual(tag_group.tags, FilterSet({Tag("a"), Tag("b:c"), Tag("d:e:f")}))

    def test_instantiation_from_tag_group(self):
        """ Test that a TagGroup can be instantiated from another TagGroup. """
        self.assertEqual(self.TAG_GROUP, TagGroup(self.TAG_GROUP))

    def test_equality(self):
        """ Ensure two TagGroups with the same tags compare equal. """
        self.assertTrue(self.TAG_GROUP == TagGroup(tags="a b:c d:e:f"))

    def test_inequality(self):
        """ Ensure two TagGroups with different tags compare unequal. """
        self.assertTrue(self.TAG_GROUP != TagGroup(tags="a"))

    def test_non_tag_groups_compare_unequal_to_tag_groups(self):
        """ Ensure a TagGroup and a non-TagGroup compare unequal. """
        self.assertFalse(self.TAG_GROUP == "a")
        self.assertTrue(self.TAG_GROUP != "a")

    def test_iterating_over(self):
        """ Ensure a TagGroup can be iterated over. """
        self.assertEqual(set(self.TAG_GROUP), {Tag("a"), Tag("b:c"), Tag("d:e:f")})

    def test_has_tag(self):
        """ Ensure we can check that a TagGroup has a certain tag. """
        self.assertTrue(self.TAG_GROUP.has_tag("d:e:f"))

    def test_does_not_have_tag(self):
        """ Ensure we can check that a TagGroup does not have a certain tag. """
        self.assertFalse(self.TAG_GROUP.has_tag("hello"))

    def test_has_tag_only_matches_full_tags(self):
        """ Test that the has_tag method only matches full tags (i.e. that it doesn't match subtags or parts of tags."""
        for tag in "a", "b:c", "d:e:f":
            self.assertTrue(self.TAG_GROUP.has_tag(tag))

        for tag in "b", "c", "d", "e", "f":
            self.assertFalse(self.TAG_GROUP.has_tag(tag))

    def test_get_subtags(self):
        """ Test subtags can be accessed as a new TagGroup. """
        self.assertEqual(TagGroup("meta:sys2:3456 blah").get_subtags(), TagGroup("meta sys2 3456 blah"))

    def test_starts_with(self):
        """ Ensure starts_with only checks the starts of tags, and doesn't check the starts of subtags. """
        for tag in "a", "b", "d":
            self.assertTrue(self.TAG_GROUP.starts_with(tag))

        for tag in "c", "e", "f":
            self.assertFalse(self.TAG_GROUP.starts_with(tag))

    def test_ends_swith(self):
        """ Ensure ends_with doesn't check ends of subtags. """
        for tag in "a", "c", "f":
            self.assertTrue(self.TAG_GROUP.ends_with(tag))

        for tag in "b", "d", "e":
            self.assertFalse(self.TAG_GROUP.ends_with(tag))

    def test_contains_searches_for_tags_and_subtags(self):
        """ Ensure tags and subtags can be searched for. """
        for tag in "a", "b", "d":
            self.assertTrue(self.TAG_GROUP.any_tag_contains(tag))

        for subtag in "c", "e", "f":
            self.assertTrue(self.TAG_GROUP.any_tag_contains(subtag))

    def test_filter(self):
        """ Test that tag groups can be filtered. """
        tag_group = TagGroup(tags="tag1 tag2 meta:sys1:1234 meta:sys2:3456 meta:sys2:55")
        self.assertEqual(
            tag_group.tags.filter("name__starts_with", "meta"),
            FilterSet({Tag("meta:sys1:1234"), Tag("meta:sys2:3456"), Tag("meta:sys2:55")}),
        )

    def test_filter_chaining(self):
        """ Test that filters can be chained. """
        tag_group = TagGroup(tags="tag1 tag2 meta:sys1:1234 meta:sys2:3456 meta:sys2:55")

        filtered_tags_1 = tag_group.tags.filter("name__starts_with", "meta")
        self.assertEqual(filtered_tags_1, TagGroup("meta:sys1:1234 meta:sys2:3456 meta:sys2:55").tags)

        filtered_tags_2 = filtered_tags_1.filter("name__contains", "sys2")
        self.assertEqual(filtered_tags_2, TagGroup("meta:sys2:3456 meta:sys2:55").tags)

        filtered_tags_3 = filtered_tags_1.filter("name__equals", "meta:sys2:55")
        self.assertEqual(filtered_tags_3, TagGroup("meta:sys2:55").tags)

    def test_serialise(self):
        """ Ensure that TagGroups are serialised to the string form of a list. """
        self.assertEqual(self.TAG_GROUP.serialise(), "['a', 'b:c', 'd:e:f']")

    def test_serialise_orders_tags(self):
        """ Ensure that TagGroups are serialised to the string form of a list. """
        tag_group = TagGroup("z hello a c:no")
        self.assertEqual(tag_group.serialise(), "['a', 'c:no', 'hello', 'z']")

    def test_str_is_equivalent_to_serialise(self):
        """ Test that calling `str` on a TagGroup is equivalent to using the `serialise` method. """
        tag_group = TagGroup("z hello a c:no")
        self.assertEqual(str(tag_group), tag_group.serialise())

    def test_repr(self):
        """ Test the representation of a TagGroup appears as expected. """
        self.assertEqual(repr(self.TAG_GROUP), f"<TagGroup({repr(self.TAG_GROUP.tags)})>")
