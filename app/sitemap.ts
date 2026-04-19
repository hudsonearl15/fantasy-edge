import type { MetadataRoute } from "next";
import { getAllPlayers, POSITIONS, PITCHER_POSITIONS } from "@/lib/data";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://fantasybaseballedge.com";
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: now, changeFrequency: "weekly", priority: 1 },
    {
      url: `${baseUrl}/compare`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${baseUrl}/sleepers`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.9,
    },
  ];

  const positionPages: MetadataRoute.Sitemap = [
    ...POSITIONS,
    ...PITCHER_POSITIONS,
  ].map((pos) => ({
    url: `${baseUrl}/rankings/${pos.toLowerCase()}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  const players = getAllPlayers();
  const playerPages: MetadataRoute.Sitemap = players.map((p) => ({
    url: `${baseUrl}/player/${p.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: p.fantasy.FPTS > 500 ? 0.7 : 0.5,
  }));

  return [...staticPages, ...positionPages, ...playerPages];
}
