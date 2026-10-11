package com.lootingbagtracker;

import com.google.common.collect.HashMultiset;
import com.google.common.collect.Multiset;
import com.google.common.collect.Multisets;
import java.util.List;
import java.util.stream.Collectors;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.Item;
import net.runelite.api.ItemContainer;
import net.runelite.api.MenuAction;
import net.runelite.api.events.GameTick;
import net.runelite.api.events.ItemContainerChanged;
import net.runelite.api.events.MenuOptionClicked;
import net.runelite.client.eventbus.EventBus;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.game.ItemStack;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.plugins.loottracker.PluginLootReceived;
import net.runelite.http.api.loottracker.LootRecordType;
import net.runelite.client.util.Text;

@Slf4j
@PluginDescriptor(
	name = "Looting Bag Loot Tracker",
	description = "Tracks loot that goes into an open looting bag during chest and container interactions",
	tags = {"loot", "tracker", "looting bag", "thieving", "chest"}
)
public class LootingBagTrackerPlugin extends Plugin
{
	// net.runelite.api.gameval.InventoryID
	private static final int INV_CONTAINER = 93;
	private static final int LOOTING_BAG_CONTAINER = 516;

	// net.runelite.api.gameval.ItemID
	private static final int ITEM_LOOTING_BAG_OPEN = 22586;

	private static final int SNAPSHOT_TIMEOUT_TICKS = 24;

	@Inject
	private Client client;

	@Inject
	private EventBus eventBus;

	private Multiset<Integer> lastKnownBagContents = HashMultiset.create();
	private String pendingSourceName;
	private int snapshotTicksRemaining;

	@Override
	protected void startUp()
	{
		lastKnownBagContents = getBagContents();
	}

	@Override
	protected void shutDown()
	{
		pendingSourceName = null;
		snapshotTicksRemaining = 0;
		lastKnownBagContents = HashMultiset.create();
	}

	@Subscribe
	public void onMenuOptionClicked(MenuOptionClicked event)
	{
		if (!playerHasOpenBag())
		{
			return;
		}

		if (!isObjectOp(event.getMenuAction()))
		{
			return;
		}

		final String option = event.getMenuOption();
		if (!option.equals("Open") && !option.equals("Unlock")
			&& !option.equals("Search") && !option.equals("Search for traps")
			&& !option.equals("Steal") && !option.equals("Loot"))
		{
			return;
		}

		final String sourceName = Text.removeTags(event.getMenuTarget());
		log.debug("Pending looting bag loot from: {}", sourceName);
		pendingSourceName = sourceName;
		snapshotTicksRemaining = SNAPSHOT_TIMEOUT_TICKS;
	}

	@Subscribe
	public void onItemContainerChanged(ItemContainerChanged event)
	{
		if (event.getContainerId() != LOOTING_BAG_CONTAINER)
		{
			return;
		}

		final Multiset<Integer> currentBag = getBagContents();

		if (pendingSourceName != null)
		{
			final List<ItemStack> gained = Multisets.difference(currentBag, lastKnownBagContents).entrySet().stream()
				.filter(e -> e.getElement() > 0)
				.map(e -> new ItemStack(e.getElement(), e.getCount()))
				.collect(Collectors.toList());

			if (!gained.isEmpty())
			{
				log.debug("Looting bag received {} item(s) from: {}", gained.size(), pendingSourceName);
				eventBus.post(PluginLootReceived.builder()
					.source(this)
					.name(pendingSourceName)
					.type(LootRecordType.EVENT)
					.items(gained)
					.build());
				pendingSourceName = null;
				snapshotTicksRemaining = 0;
			}
		}

		lastKnownBagContents = currentBag;
	}

	@Subscribe
	public void onGameTick(GameTick tick)
	{
		if (snapshotTicksRemaining > 0 && --snapshotTicksRemaining == 0)
		{
			log.debug("Looting bag pending interaction timed out");
			pendingSourceName = null;
		}
	}

	private Multiset<Integer> getBagContents()
	{
		final Multiset<Integer> contents = HashMultiset.create();
		final ItemContainer bag = client.getItemContainer(LOOTING_BAG_CONTAINER);
		if (bag != null)
		{
			for (Item item : bag.getItems())
			{
				if (item.getId() > 0)
				{
					contents.add(item.getId(), item.getQuantity());
				}
			}
		}
		return contents;
	}

	private boolean playerHasOpenBag()
	{
		final ItemContainer inv = client.getItemContainer(INV_CONTAINER);
		return inv != null && inv.contains(ITEM_LOOTING_BAG_OPEN);
	}

	private static boolean isObjectOp(MenuAction action)
	{
		final int id = action.getId();
		return (id >= MenuAction.GAME_OBJECT_FIRST_OPTION.getId()
			&& id <= MenuAction.GAME_OBJECT_FOURTH_OPTION.getId())
			|| id == MenuAction.GAME_OBJECT_FIFTH_OPTION.getId();
	}
}
