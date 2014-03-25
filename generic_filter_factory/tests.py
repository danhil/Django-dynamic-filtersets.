"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from .models import User

class SimpleTest(TestCase):
    def test_basic_addition(self):
        User.objects.create(username='alex', is_active=False)
        """
        Tests that 1 + 1 always equals 2.
        """
        print "TESTING"
        self.assertEqual(1 , 2)
