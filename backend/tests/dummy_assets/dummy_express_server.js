const express = require('express');
const mongoose = require('mongoose');
const router = express.Router();

// Mongoose Schema & Model
const userSchema = new mongoose.Schema({
  name: String,
  email: String
});
const User = mongoose.model('User', userSchema);

// Express Routes
router.get('/users', async (req, res) => {
  const users = await User.find();
  res.json(users);
});

router.post('/users', async (req, res) => {
  const newUser = new User(req.body);
  await newUser.save();
  res.status(201).json(newUser);
});

// React Component
function UserProfile({ userId }) {
  return (
    <div className="user-profile">
      <h2>User Profile</h2>
    </div>
  );
}

const UserCard = ({ user }) => {
  return <div>{user.name}</div>;
};

module.exports = { User, UserProfile, UserCard };
