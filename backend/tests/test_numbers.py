from app.analysis.numbers import (
    build_comparisons,
    compare_group,
    extract_numbers,
    group_observations,
    is_internally_consistent,
    observations_about_the_event,
)
from app.models.enums import ValueKind


def extract(text: str, article_id: int = 1, source_id: int = 1):
    return extract_numbers(article_id, source_id, "Report on the plant incident", text)


def test_percentage_is_recognised_as_a_level():
    observation = extract("Air quality monitors recorded readings above the limit at 30% of stations.")[0]
    assert observation.value == 30.0
    assert observation.value_kind is ValueKind.PERCENT
    assert observation.unit == "%"


def test_percentage_points_are_kept_distinct_from_percent():
    observation = extract("The share rose by 10 percentage points over the period.")[0]
    assert observation.value_kind is ValueKind.PERCENTAGE_POINT
    assert observation.unit == "percentage points"


def test_change_verb_turns_a_percentage_into_a_change():
    observation = extract("Shares in Vantor Industries fell 6.2% on Tuesday.")[0]
    assert observation.value_kind is ValueKind.PERCENT_CHANGE


def test_scale_words_are_applied():
    observation = extract("The company reported a 4.5 million dollars charge for the quarter.")[0]
    assert observation.value == 4_500_000
    assert observation.value_kind is ValueKind.CURRENCY


def test_currency_symbol_is_recognised():
    observation = extract("The regulator issued a $2 million fine to the operator.")[0]
    assert observation.value == 2_000_000
    assert observation.unit == "USD"


def test_thousands_separator_is_parsed():
    observation = extract("County records show that 3,200 residents were evacuated from the area.")[0]
    assert observation.value == 3200.0
    assert observation.unit == "residents"


def test_bare_years_are_not_treated_as_measurements():
    assert extract("A valve at the plant had not been inspected since 2023.") == []


def test_calendar_dates_are_not_treated_as_measurements():
    assert extract("The strike began on 15 February and lasted eleven days.") == []


def test_clock_times_are_not_treated_as_measurements():
    assert extract("Operators reported the release shortly after 05:00 local time.") == []


def test_matching_subjects_are_compared():
    left = extract("County records show that 3,200 residents were evacuated from the area.", 1, 1)
    right = extract("About 4,000 residents were evacuated from the area.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison.lowest == 3200
    assert comparison.highest == 4000
    assert comparison.difference == 800
    assert comparison.sources_agree is False


def test_percent_difference_is_expressed_in_percentage_points():
    left = extract("Readings were above the limit at 30% of measurement stations.", 1, 1)
    right = extract("Readings were above the limit at 20% of measurement stations.", 2, 2)
    comparison = build_comparisons(left + right)[0]
    assert comparison.difference == 10
    assert comparison.difference_unit == "percentage points"


def test_unrelated_numbers_with_the_same_unit_are_not_compared():
    evacuated = extract("About 4,000 residents were evacuated from the area.", 1, 1)
    attending = extract("About 4,000 residents attended the county meeting last year.", 2, 2)
    groups = group_observations(evacuated + attending)
    assert all(len({item.article_id for item in group}) == 1 for group in groups)


def test_different_units_are_never_compared():
    tonnes = extract("The release involved about 12 tonnes of industrial solvent.", 1, 1)
    residents = extract("About 12 residents were treated at the scene.", 2, 2)
    assert build_comparisons(tonnes + residents) == []


def test_same_article_reporting_two_values_invalidates_a_group():
    votes = extract("The council voted to approve the plan by 21 votes to 14 votes.", 1, 1)
    more_votes = extract("The council voted to approve the plan by 21 votes to 14 votes.", 2, 2)
    assert {item.value for item in votes} == {21, 14}
    assert not is_internally_consistent(votes + more_votes)
    grouped = group_observations(votes + more_votes)
    assert all(is_internally_consistent(group) for group in grouped if len(group) > 1)
    assert all(c.sources_agree for c in build_comparisons(votes + more_votes))


def test_ordinals_scores_and_stage_labels_are_not_measurements():
    text = (
        "The 1,000th FIFA World Cup match is held in Monterrey, with Japan defeating "
        "Tunisia 4–0. Paraguay defeated Germany 4–3 on penalties in the round of 32."
    )
    assert extract(text) == []


def test_bare_number_without_a_counted_noun_is_skipped():
    assert extract("Ivory Coast finished the group stage on 7.") == []
    observation = extract("Rebels shelled the town, displacing 300 families overnight.")[0]
    assert observation.value == 300


def test_ages_of_different_people_are_not_compared():
    attacker = extract("A day later, a 15-year-old killed a school caretaker.", 1, 1)
    victim = extract("A day later, the 37-year-old caretaker was killed at the school.", 2, 2)
    assert build_comparisons(attacker + victim) == []


def test_storm_category_is_a_label_not_an_amount():
    assert extract("Isaias made landfall as a Category 2 storm near Destin.") == []


def test_abbreviated_month_dates_are_not_split_into_numbers():
    assert extract("The ceasefire took effect on Oct. 10, 2025, after the Oct. 7 massacre.") == []


def test_figure_from_an_earlier_moment_is_not_set_against_todays():
    today = extract("The attack on the airport on Saturday left at least 12 people dead.", 1, 1)
    earlier = extract("It comes a day after a strike on the same airport killed 13 people.", 2, 2)
    assert build_comparisons(today + earlier) == []


def test_an_increment_is_not_a_total():
    assert extract("The agency revised its toll after 30 more bodies were recovered.") == []


def test_page_clutter_is_not_quoted_as_a_claim():
    assert extract("Read more at https://example.com/story about the 300 people evacuated.") == []


def test_different_actions_on_the_same_people_are_not_compared():
    rescued = extract("More than 8,100 people in Nepal have been rescued, officials said.", 1, 1)
    affected = extract("As many as 93,000 people in Nepal have been affected by the disaster.", 2, 2)
    assert build_comparisons(rescued + affected) == []


def test_another_storys_headline_on_the_page_is_dropped():
    shipwreck = "At least 139 people died when a boat capsized off the coast in Djibouti."
    other_story = "Children among 9 dead in a shooting in Pennsylvania."
    documents = [
        (1, f"{shipwreck} {other_story}"),
        (2, "The boat capsized near Obock in Djibouti, the UN said."),
    ]
    observations = extract(shipwreck, 1, 1) + extract(other_story, 1, 1)
    kept = observations_about_the_event(observations, documents)
    assert [observation.value for observation in kept] == [139]


def test_price_moves_without_a_stated_period_are_not_compared():
    one_day = extract("Brent crude futures gained about 1.3% to close at the session high.", 1, 1)
    another_day = extract("Brent crude futures gained more than 3% to close at the session high.", 2, 2)
    assert build_comparisons(one_day + another_day) == []


def test_missing_and_rescued_people_are_not_compared():
    missing = extract("Officials said 558 people were missing, including 260 foreign nationals.", 1, 1)
    rescued = extract("The Nepal Tourism Board said 261 foreign nationals have been rescued.", 2, 2)
    assert build_comparisons(missing + rescued) == []


def test_world_cup_milestone_and_stage_are_never_compared():
    milestone = extract("The 1,000th FIFA World Cup match is held at Estadio BBVA.", 1, 1)
    stage = extract("Paraguay defeated Germany in the FIFA World Cup round of 32.", 2, 2)
    assert build_comparisons(milestone + stage) == []


def test_agreement_is_reported_when_sources_match():
    left = extract("About 240 workers were on site at the time of the release.", 1, 1)
    right = extract("About 240 workers were on site at the time of the release.", 2, 2)
    comparison = build_comparisons(left + right)[0]
    assert comparison.sources_agree is True
    assert comparison.difference == 0


def test_comparison_requires_two_sources():
    single = extract("About 240 workers were on site at the time of the release.", 1, 1)
    assert build_comparisons(single) == []


def test_compare_group_reports_relative_difference_for_counts():
    left = extract("About 1,800 workers took part in the strike.", 1, 1)
    right = extract("About 2,000 workers took part in the strike.", 2, 2)
    group = group_observations(left + right)[0]
    comparison = compare_group(group)
    assert comparison.relative_difference_percent == 11.11


def test_killed_is_not_read_as_thousands():
    observation = extract("Medics said 21 killed when the building collapsed.")[0]
    assert observation.value == 21.0
    assert observation.subject_tokens == ("death", "person")


def test_compact_k_scale_still_applies():
    observation = extract("The plant stored 21k barrels of solvent.")[0]
    assert observation.value == 21_000.0


def test_death_counts_are_compared_despite_wording():
    left = extract("The collapse killed at least 20 people in the building.", 1, 1)
    right = extract("Medics said 21 killed in the Gaza building collapse.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    assert comparisons[0].lowest == 20
    assert comparisons[0].highest == 21
    assert comparisons[0].sources_agree is False


def test_nearby_non_death_counts_are_not_treated_as_fatalities():
    observations = extract("The strike was killing people from 6 displaced families.")
    death_values = [item.value for item in observations if item.subject_tokens == ("death", "person")]
    assert 6.0 not in death_values


def test_strike_death_tolls_from_two_outlets_are_compared():
    left = extract("Officials said the Iranian strike killed 100 people overnight.", 1, 1)
    right = extract("At least 150 people were killed in the Iranian strike, the ministry said.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    assert (comparisons[0].lowest, comparisons[0].highest) == (100, 150)
    assert comparisons[0].sources_agree is False


def test_spelled_out_death_toll_is_read():
    observation = extract("Twenty-one people are killed after a building collapses.")[0]
    assert observation.value == 21.0
    assert observation.subject_tokens == ("death", "person")


def test_spelled_out_numbers_are_ignored_outside_casualty_counts():
    assert extract("The talks lasted three days and covered five topics.") == []


def test_number_after_killed_can_still_be_an_injury_count():
    observations = extract("Twenty-one people are killed, 45 are injured, and others are missing.")
    by_value = {item.value: item.subject_tokens for item in observations}
    assert by_value[21.0] == ("death", "person")
    assert by_value[45.0] == ("injury", "person")


def test_wounded_counts_as_injured():
    left = extract("The attack left more than 300 wounded, Saudi authorities said.", 1, 1)
    right = extract("Hospitals were treating 309 people injured in the attack.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    assert comparisons[0].observations[0].subject_tokens == ("injury", "person")


def test_soldier_and_civilian_tolls_are_never_compared():
    left = extract("The shelling killed 30 civilians near the border.", 1, 1)
    right = extract("The shelling killed 12 soldiers near the border.", 2, 2)
    assert build_comparisons(left + right) == []


def test_war_total_is_not_compared_with_a_single_strike():
    left = extract("Since the war began, more than 150,000 people have died.", 1, 1)
    right = extract("The strike on the market killed 30 people.", 2, 2)
    assert left[0].time_period == "since the war began"
    assert build_comparisons(left + right) == []


def test_war_totals_are_compared_with_each_other():
    left = extract("More than 150,000 people have died since the war began.", 1, 1)
    right = extract("Some 200,000 people have been killed since the start of the war.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    assert comparisons[0].time_period == "since the war began"


def test_age_and_duration_next_to_died_are_not_death_counts():
    observations = extract("Shakur died six days later. He was killed at 25 during his career.")
    assert not [item for item in observations if item.subject_tokens[0] == "death"]


def test_background_toll_in_the_same_article_does_not_block_the_comparison():
    left = extract(
        "The collapse killed at least 21 people. The war began when about 1,200 people were killed.", 1, 1
    )
    right = extract("The building collapse killed at least 20 people.", 2, 2)
    comparisons = build_comparisons(left + right)
    assert len(comparisons) == 1
    assert (comparisons[0].lowest, comparisons[0].highest) == (20, 21)


def test_groups_of_different_magnitude_get_different_keys():
    observations = extract("The strike killed 12 people.", 1, 1) + extract("The strike killed 13 people.", 2, 2)
    observations += extract("The war has killed 1,200 people.", 3, 3) + extract("The war has killed 1,300 people.", 4, 4)
    keys = {comparison.comparison_key for comparison in build_comparisons(observations)}
    assert len(keys) == 2


def test_rising_death_toll_is_a_death_count():
    observation = extract("The death toll from the missile attack rose to 22, the governor said.")[0]
    assert observation.subject_tokens == ("death", "person")


def test_repeated_headline_is_not_counted_twice():
    observations = extract_numbers(
        1,
        1,
        "21 killed as Gaza building collapses",
        "21 killed as Gaza building collapses. Medics said 21 killed when the building collapsed.",
    )
    deaths = [item for item in observations if item.subject_tokens == ("death", "person")]
    assert len(deaths) == 1
    assert deaths[0].value == 21.0
