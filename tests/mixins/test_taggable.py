from octue import exceptions
from octue.mixins import MixinBase, Taggable
from octue.mixins.taggable import TagGroup
from ..base import BaseTestCase


class MyTaggable(Taggable, MixinBase):
    pass


class TaggableTestCase(BaseTestCase):
    def test_instantiates(self):
        """ Ensures the class instantiates without arguments
        """
        Taggable()

    def test_instantiates_with_tags(self):
        """ Ensures datafile inherits correctly from the Taggable class and passes arguments through
        """
        tgd = MyTaggable(tags="")
        self.assertEqual("", str(tgd.tags))
        tgd = MyTaggable(tags=None)
        self.assertEqual("", str(tgd.tags))
        tgd = MyTaggable(tags="a b c")
        self.assertEqual("a b c", str(tgd.tags))
        with self.assertRaises(exceptions.InvalidTagException):
            MyTaggable(tags=":a b c")

    def test_instantiates_with_tag_group(self):
        """ Ensures datafile inherits correctly from the Taggable class and passes arguments through
        """
        tgd = MyTaggable(tags="")
        self.assertIsInstance(tgd.tags, TagGroup)
        tgd2 = MyTaggable(tags=tgd.tags)
        self.assertFalse(tgd is tgd2)

    def test_fails_to_instantiates_with_non_iterable(self):
        """ Ensures datafile inherits correctly from the Taggable class and passes arguments through
        """

        class NoIter:
            pass

        with self.assertRaises(exceptions.InvalidTagException) as error:
            MyTaggable(tags=NoIter())

        self.assertIn(
            "Tags must be expressed as a whitespace-delimited string or an iterable of strings", error.exception.args[0]
        )

    def test_reset_tags(self):
        """ Ensures datafile inherits correctly from the Taggable class and passes arguments through
        """
        tgd = MyTaggable(tags="a b")
        tgd.tags = "b c"
        self.assertEqual(str(tgd.tags), "b c")

    def test_valid_tags(self):
        """ Ensures valid tags do not raise an error
        """
        tgd = MyTaggable()
        tgd.add_tags("a-valid-tag")
        tgd.add_tags("a:tag")
        tgd.add_tags("a:-tag")  # <--- yes, this is valid deliberately as it allows people to do negation
        tgd.add_tags("a1829tag")
        tgd.add_tags("1829")
        tgd.add_tags("number:1829")
        tgd.add_tags("multiple:discriminators:used")
        self.assertEqual(
            str(tgd.tags), "a-valid-tag a:tag a:-tag a1829tag 1829 number:1829 multiple:discriminators:used"
        )

    def test_invalid_tags(self):
        """ Ensures invalid tags raise an error
        """
        tgd = MyTaggable()
        with self.assertRaises(exceptions.InvalidTagException):
            tgd.add_tags("-bah")

        with self.assertRaises(exceptions.InvalidTagException):
            tgd.add_tags("humbug:")

        with self.assertRaises(exceptions.InvalidTagException):
            tgd.add_tags("SHOUTY")

        with self.assertRaises(exceptions.InvalidTagException):
            tgd.add_tags(r"back\slashy")

        with self.assertRaises(exceptions.InvalidTagException):
            tgd.add_tags({"not-a": "string"})

    def test_mixture_valid_invalid(self):
        """ Ensures that adding a variety of tags, some of which are invalid, doesn't partially add them to the object
        """
        tgd = MyTaggable()
        tgd.add_tags("first-valid-should-be-added")
        try:
            tgd.add_tags("second-valid-should-not-be-added-because", "-the-third-is-invalid:")

        except exceptions.InvalidTagException:
            pass

        self.assertEqual("first-valid-should-be-added", str(tgd.tags))

    def test_serialises_to_string(self):
        """ Ensures that adding a variety of tags, some of which are invalid, doesn't partially add them to the object
        """
        tgd = Taggable(tags="a b")
        self.assertEqual("a b", tgd.tags.serialise())


class TestTagGroup(BaseTestCase):
    def test_yield_subtags(self):
        """ Test that subtags can be yielded from tags, including the main tags themselves. """
        tag_group = TagGroup(tags="a b:c d:e:f")
        self.assertEqual(list(tag_group.yield_subtags()), ["a", "b", "c", "d", "e", "f"])

    def test_contains_magic_method_only_matches_full_tags(self):
        """ Test that the __contains__ method only matches full tags (i.e. that it doesn't match subtags or parts of
        tags.
        """
        tag_group = TagGroup(tags="a b:c d:e:f")
        self.assertIn("a", tag_group)
        self.assertIn("b:c", tag_group)
        self.assertIn("d:e:f", tag_group)
        self.assertNotIn("b", tag_group)
        self.assertNotIn("c", tag_group)
        self.assertNotIn("d", tag_group)
        self.assertNotIn("e", tag_group)
        self.assertNotIn("f", tag_group)

    def test_contains_searches_for_tags_and_subtags(self):
        """ Ensure tags and subtags can be searched for. """
        tag_group = TagGroup(tags="a b:c d:e:f")

        for tag in "a", "b", "d":
            self.assertTrue(tag_group.contains(tag))

        for subtag in "c", "e", "f":
            self.assertTrue(tag_group.contains(subtag))
