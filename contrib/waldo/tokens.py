"""
Based on django.contrib.auth.tokens
"""


from datetime import date
from django.conf import settings
from django.utils.http import int_to_base36, base36_to_int
from django.contrib.auth.tokens import PasswordResetTokenGenerator


REGISTRATION_TIMEOUT_DAYS = getattr(settings, 'WALDO_REGISTRATION_TIMEOUT_DAYS', 1)


class RegistrationTokenGenerator(PasswordResetTokenGenerator):
	"""
	Strategy object used to generate and check tokens for the user registration mechanism.
	"""
	def make_token(self, user):
		"""
		Returns a token that can be used once to activate a user's account.
		"""
		if user.is_active:
			return False
		return self._make_token_with_timestamp(user, self._num_days(self._today()))
	
	def check_token(self, user, token):
		"""
		Check that a registration token is correct for a given user.
		"""
		# If the user is active, the hash can't be valid.
		if user.is_active:
			return False
		
		# Parse the token
		try:
			ts_b36, hash = token.split('-')
		except ValueError:
			return False
		
		try:
			ts = base36_to_int(ts_b36)
		except ValueError:
			return False
		
		# Check that the timestamp and uid have not been tampered with.
		if self._make_token_with_timestamp(user, ts) != token:
			return False
		
		# Check that the timestamp is within limit
		if (self._num_days(self._today()) - ts) > REGISTRATION_TIMEOUT_DAYS:
			return False
		
		return True
	
	def _make_token_with_timestamp(self, user, timestamp):
		ts_b36 = int_to_base36(timestamp)
		
		# By hashing on the internal state of the user and using state that is
		# sure to change, we produce a hash that will be invalid as soon as it
		# is used.
		from django.utils.hashcompat import sha_constructor
		hash = sha_constructor(settings.SECRET_KEY + unicode(user.id) + unicode(user.is_active) + user.last_login.strftime('%Y-%m-%d %H:%M:%S') + unicode(timestamp)).hexdigest()[::2]
		return '%s-%s' % (ts_b36, hash)

registration_token_generator = RegistrationTokenGenerator()