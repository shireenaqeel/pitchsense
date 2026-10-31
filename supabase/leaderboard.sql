-- The quiz leaderboard, for the deployed app (see src/pitchsense/leaderboard.py).
-- Run once in the Supabase SQL editor of the PitchSense project.
--
-- The app talks to this table with the project's publishable (anon) key, so the
-- rules that matter live here, not in the app: the key can read and insert, never
-- update or delete; every row must look like a real quiz result; and inserts are
-- throttled for everyone together, so even a leaked key can't flood the board.

create table if not exists public.leaderboard (
  id          bigint generated always as identity primary key,
  name        text    not null check (char_length(name) between 1 and 20),
  rounds      integer not null check (rounds between 1 and 1000),
  avg_points  numeric not null check (avg_points between 0 and 100),
  model_avg   numeric not null check (model_avg between 0 and 100),
  vs_model    numeric not null check (vs_model between -100 and 100),
  date        date    not null default current_date,
  created_at  timestamptz not null default now()
);

create index if not exists leaderboard_rank
  on public.leaderboard (avg_points desc, vs_model desc, rounds desc);

alter table public.leaderboard enable row level security;

drop policy if exists "Anyone can read the board" on public.leaderboard;
create policy "Anyone can read the board"
  on public.leaderboard for select
  to anon
  using (true);

drop policy if exists "Anyone can add a score" on public.leaderboard;
create policy "Anyone can add a score"
  on public.leaderboard for insert
  to anon
  with check (date between current_date - 1 and current_date + 1);

-- At most 30 new rows a minute across everyone; the app itself allows 10.
create or replace function public.leaderboard_throttle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select count(*) from public.leaderboard
      where created_at > now() - interval '1 minute') >= 30 then
    raise exception 'leaderboard is rate limited, try again in a minute';
  end if;
  new.created_at := now();
  return new;
end;
$$;

drop trigger if exists leaderboard_throttle on public.leaderboard;
create trigger leaderboard_throttle
  before insert on public.leaderboard
  for each row execute function public.leaderboard_throttle();

-- Only the columns the app sends can be written; id and created_at are the
-- database's own.
revoke all on public.leaderboard from anon, authenticated;
grant select on public.leaderboard to anon;
grant insert (name, rounds, avg_points, model_avg, vs_model, date) on public.leaderboard to anon;
