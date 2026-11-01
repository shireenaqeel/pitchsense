-- The browser game's shared leaderboards: each day's Daily Challenge, and
-- Rapid Fire of all time (see game/src/systems/leaderboard.ts). Run once in the
-- Supabase SQL editor of the PitchSense project, after leaderboard.sql.
--
-- The game runs in the player's browser, so it carries the project's
-- publishable key, and anyone can find it. That is what the key is for: on its
-- own it can only do what these rules allow. It can read scores and add new
-- ones, never change or delete them; every row must be a possible result; and
-- inserts are throttled for everyone together. A determined player could still
-- post a made-up score within those limits, as with any game that scores in the
-- browser.

create table if not exists public.game_scores (
  id          bigint generated always as identity primary key,
  mode        text    not null check (mode in ('daily', 'rapid')),
  day         date,
  name        text    not null check (char_length(name) between 1 and 20),
  score       integer not null check (score >= 0),
  reads       integer not null check (reads between 1 and 1000),
  created_at  timestamptz not null default now(),
  -- A daily is 10 shots worth at most 250 each, and belongs to a day; Rapid
  -- Fire has no day, and a 60-second clock that good reads extend.
  constraint game_scores_shape check (
    (mode = 'daily' and day is not null and reads = 10 and score <= 2500) or
    (mode = 'rapid' and day is null and score <= 100000)
  )
);

create index if not exists game_scores_rank
  on public.game_scores (mode, day, score desc, created_at);

alter table public.game_scores enable row level security;

drop policy if exists "Anyone can read the boards" on public.game_scores;
create policy "Anyone can read the boards"
  on public.game_scores for select
  to anon
  using (true);

-- A daily can only be posted for today, give or take a day for time zones.
drop policy if exists "Anyone can add a score" on public.game_scores;
create policy "Anyone can add a score"
  on public.game_scores for insert
  to anon
  with check (day is null or day between current_date - 1 and current_date + 1);

-- At most 30 new rows a minute across everyone.
create or replace function public.game_scores_throttle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select count(*) from public.game_scores
      where created_at > now() - interval '1 minute') >= 30 then
    raise exception 'the leaderboard is rate limited, try again in a minute';
  end if;
  new.created_at := now();
  return new;
end;
$$;

drop trigger if exists game_scores_throttle on public.game_scores;
create trigger game_scores_throttle
  before insert on public.game_scores
  for each row execute function public.game_scores_throttle();

-- Only the columns the game sends can be written.
revoke all on public.game_scores from anon, authenticated;
grant select on public.game_scores to anon;
grant insert (mode, day, name, score, reads) on public.game_scores to anon;
