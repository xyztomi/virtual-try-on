## Virtual Try-On Project

### Development Setup

#### 1. Clone the repository
```bash
git clone https://github.com/xyztomi/virtual-try-on
cd virtual-try-on
```

#### 2. Install dependencies
TODO: Add installation instructions for frontend and backend dependencies.

#### 3. Start development server
*Frontend:*  
TODO: Add instructions to start the frontend development server.

*Backend:*  
TODO: Add instructions to start the backend development server.

---


### Git Workflow & Branching

1. **Branches:**
	 - `main`: production-ready.
	 - `frontend`: All frontend work happens here.
	 - `backend`: All backend work happens here.

2. **How to create and update your branch:**
	 - Create your branch (if not exists):
		 ```bash
		 git checkout -b frontend   # or backend
		 git push -u origin frontend  # or backend
		 ```
	 - Switch to your branch:
		 ```bash
		 git checkout frontend   # or backend
		 ```
	 - Pull latest changes from main into your branch:
		 ```bash
		 git checkout main
		 git pull origin main
		 git checkout frontend   # or backend
		 git merge main
		 ```

3. **Merging to main:**
	 - Only the project owner (xyztomi) should merge to `main`.
	 - When your work is ready, push your branch and open a pull request (PR) to `main`.
	 - The owner reviews and merges the PR.

4. **Commit often:** Use clear, concise commit messages.

---

---
