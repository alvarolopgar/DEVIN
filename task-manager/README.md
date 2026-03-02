# Task Manager

A full-stack task manager application built with **Next.js**, **Tailwind CSS**, and **Supabase**.

## Features

- Google Authentication via Supabase Auth
- User-specific tasks with Row Level Security (RLS)
- Create, edit, delete, and update task status
- Filter tasks by status (Pending, In Progress, Completed)
- Search tasks by title or description
- Task priority levels (Low, Medium, High)
- Clean, responsive UI with Tailwind CSS
- Real-time task statistics dashboard

## Tech Stack

- **Frontend**: Next.js 16 (App Router), React 19, Tailwind CSS 4
- **Backend**: Supabase (PostgreSQL + Auth + RLS)
- **Authentication**: Google OAuth via Supabase
- **Deployment**: Vercel

## Setup

### 1. Supabase Project

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the schema from `supabase/schema.sql`
3. Go to **Authentication > Providers** and enable **Google** provider
4. Configure Google OAuth credentials in the Google Cloud Console
5. Copy your Supabase URL and anon key from **Settings > API**

### 2. Environment Variables

Copy the example env file and fill in your values:

```bash
cp .env.local.example .env.local
```

Required variables:
- `NEXT_PUBLIC_SUPABASE_URL` - Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Your Supabase anon/public key

### 3. Run Locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Deploy to Vercel

1. Push this repo to GitHub
2. Import the project in [Vercel](https://vercel.com)
3. Set the **Root Directory** to `task-manager`
4. Add environment variables (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
5. Deploy!

Make sure to add your Vercel deployment URL to Supabase:
- **Authentication > URL Configuration > Site URL**: `https://your-app.vercel.app`
- **Authentication > URL Configuration > Redirect URLs**: `https://your-app.vercel.app/auth/callback`

## Database Schema

The `tasks` table includes:
- `id` (UUID, primary key)
- `user_id` (UUID, references auth.users)
- `title` (text, required)
- `description` (text, optional)
- `status` (pending | in_progress | completed)
- `priority` (low | medium | high)
- `created_at` (timestamp)
- `updated_at` (timestamp)

Row Level Security ensures each user can only access their own tasks.
