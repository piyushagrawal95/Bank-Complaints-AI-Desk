CREATE table if not exists subscriptions(
    user_id BIGINT PRIMARY KEY references users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT unique,
    stripe_subscription_id text unique,
    plan text not null default 'free' CHECK (plan IN ('free','pro')),
    status TEXT not null default 'none',
    current_period_end timestamptz,
    cancel_at_period_end boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_subscriptions_customer on subscriptions(stripe_customer_id);


--Processed Stripe Webhook events
create table if not exists stripe_events(
    event_id text primary key,
    event_type text not null,
    processed_at timestamptz not null default now()
)