from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        if not user.username:
            first = user.first_name.strip()
            last = user.last_name.strip()
            base = first[:1] + last if first and last else first or last or user.email.split('@')[0]
            user.username = self.generate_unique_username([base])
