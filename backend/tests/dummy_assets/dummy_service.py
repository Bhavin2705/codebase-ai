class UserService:
    def __init__(self, db):
        self.db = db

    async def fetch_user(self, user_id: int):
        return {"id": user_id, "name": "Test User"}
