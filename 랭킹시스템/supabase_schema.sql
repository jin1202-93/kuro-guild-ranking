CREATE TABLE IF NOT EXISTS public.guild_ranking_members_v1 (
    discord_user_id text PRIMARY KEY,
    nickname text NOT NULL,
    level integer NOT NULL DEFAULT 0 CHECK (level >= 0 AND level <= 9999),
    damage_jo bigint NOT NULL DEFAULT 0 CHECK (damage_jo >= 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS guild_ranking_members_v1_nickname_idx
    ON public.guild_ranking_members_v1 (lower(nickname));

CREATE TABLE IF NOT EXISTS public.guild_ranking_settings_v1 (
    guild_id text PRIMARY KEY,
    channel_id text NOT NULL,
    message_id text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.set_guild_ranking_updated_at_v1()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guild_ranking_members_updated_at_v1
    ON public.guild_ranking_members_v1;
CREATE TRIGGER guild_ranking_members_updated_at_v1
    BEFORE UPDATE ON public.guild_ranking_members_v1
    FOR EACH ROW EXECUTE FUNCTION public.set_guild_ranking_updated_at_v1();

DROP TRIGGER IF EXISTS guild_ranking_settings_updated_at_v1
    ON public.guild_ranking_settings_v1;
CREATE TRIGGER guild_ranking_settings_updated_at_v1
    BEFORE UPDATE ON public.guild_ranking_settings_v1
    FOR EACH ROW EXECUTE FUNCTION public.set_guild_ranking_updated_at_v1();

ALTER TABLE public.guild_ranking_members_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guild_ranking_settings_v1 ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.guild_ranking_members_v1,
    public.guild_ranking_settings_v1 FROM anon, authenticated;
GRANT ALL ON public.guild_ranking_members_v1,
    public.guild_ranking_settings_v1 TO service_role;