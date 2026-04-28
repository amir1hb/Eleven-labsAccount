-- Run this once in the Supabase SQL Editor.

create table if not exists accounts (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  mailbox_password text not null,         -- PinMX login password
  elevenlabs_password text not null,      -- elevenlabs.io login password
  domain text not null,
  status text not null check (status in ('pending','active','failed')),
  error text,
  created_by bigint not null,             -- telegram user id
  created_at timestamptz not null default now(),
  verified_at timestamptz,
  failed_at timestamptz
);

create index if not exists accounts_created_by_idx on accounts(created_by);
create index if not exists accounts_status_idx on accounts(status);
create index if not exists accounts_created_at_idx on accounts(created_at desc);

create table if not exists allowed_users (
  telegram_user_id bigint primary key,
  role text not null check (role in ('admin','user')) default 'user',
  added_by bigint,
  added_at timestamptz not null default now()
);
