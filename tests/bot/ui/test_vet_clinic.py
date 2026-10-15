"""Contract tests for src/bot/ui/vet_clinic.py."""

from math import ceil
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.vet_clinic import (
    BreedListPageSource,
    DiseaseListPageSource,
    InjuryListPageSource,
    MutationListPageSource,
    VetClinicView,
    _PatientRoomView,
    _TreatDiseaseSelectView,
)


def _make_breed(id=1, name="Poodle"):
    from src.game.models.breed import Breed

    return Breed(
        id=id,
        name=name,
        alt_name="",
        category="water_dog",
        description="A fancy dog.",
        rarity="common",
        min_size=30,
        max_size=50,
    )


def _make_mutation(id=1, name="Cataracts"):
    from src.game.models.mutation import Mutation

    return Mutation(
        id=id,
        name=name,
        alt_name="",
        category="blindness",
        description="Vision loss.",
        heritability=0.5,
        health_impact="moderate_negative",
        rarity="uncommon",
        affects_females=True,
        affects_males=True,
    )


@pytest.mark.contract
class TestVetClinicView:
    async def test_creates_view(self):
        view = VetClinicView(owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_list_breeds_button(self):
        view = VetClinicView(owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "List Breeds" for b in buttons)

    async def test_has_list_mutations_button(self):
        view = VetClinicView(owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "List Mutations" for b in buttons)

    async def test_interaction_check_owner_only(self):
        view = VetClinicView(owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestBreedListPageSource:
    async def test_empty_breeds(self):
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=[]):
            source = BreedListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No breeds found" in embed.description

    async def test_breeds_pagination(self):
        breeds = [_make_breed(id=i, name=f"Breed{i}") for i in range(25)]
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=breeds):
            source = BreedListPageSource()
            await source.load()
            assert source.page_count() == ceil(25 / 10)

    async def test_render_page(self):
        breeds = [_make_breed(id=1, name="Labrador"), _make_breed(id=2, name="Pug")]
        with patch("src.bot.ui.vet_clinic.list_all_breeds", new_callable=AsyncMock, return_value=breeds):
            source = BreedListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Labrador" in embed.description
            assert "Pug" in embed.description


@pytest.mark.contract
class TestMutationListPageSource:
    async def test_empty_mutations(self):
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=[]):
            source = MutationListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No mutations found" in embed.description

    async def test_mutations_pagination(self):
        mutations = [_make_mutation(id=i, name=f"Mut{i}") for i in range(15)]
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=mutations):
            source = MutationListPageSource()
            await source.load()
            assert source.page_count() == ceil(15 / 10)

    async def test_render_page(self):
        mutations = [_make_mutation(id=1, name="Blindness")]
        with patch("src.bot.ui.vet_clinic.list_all_mutations", new_callable=AsyncMock, return_value=mutations):
            source = MutationListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Blindness" in embed.description


@pytest.mark.contract
class TestTreatInjurySelectView:
    def _make_pi(self, id, name, visible, symptom=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            id=id,
            injury=SimpleNamespace(name=name, severity="minor"),
            visible=visible,
            displayed_symptom=symptom,
            last_treated_at=None,
            treated=False,
            persistence=3,
        )

    async def test_hidden_injury_shows_symptom_not_name(self):
        from types import SimpleNamespace

        from src.bot.ui.vet_clinic import _TreatInjurySelectView

        instances = [
            self._make_pi(1, "Sprain", visible=True),
            self._make_pi(2, "Internal Bleeding", visible=False, symptom="a pale gum"),
        ]
        view = _TreatInjurySelectView(100, SimpleNamespace(id=5, name="Rex"), instances)
        embed = await view.build_embed()
        labels = [opt.label for opt in view._select.options]

        assert "Sprain" in embed.description
        assert "a pale gum" in embed.description
        assert "Internal Bleeding" not in embed.description
        assert labels == ["Sprain", "a pale gum"]


def _make_injury_mock(id=1, name="Bruise"):
    injury = MagicMock()
    injury.id = id
    injury.name = name
    return injury


def _make_pooch_mock(name="Rex", injuries=None, diseases=None, mutations=None, diseases_list=None):
    pooch = MagicMock()
    pooch.id = 1
    pooch.name = name
    pooch.vet_checked = False
    pooch.injuries = injuries or []
    pooch.diseases = diseases_list or []
    pooch.mutations = mutations or []
    return pooch


# ---------------------------------------------------------------------------
# InjuryListPageSource
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestInjuryListPageSource:
    async def test_empty_injuries(self):
        with patch("src.bot.ui.vet_clinic.list_all_injuries", new_callable=AsyncMock, return_value=[]):
            source = InjuryListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No injuries found" in embed.description

    async def test_injury_pagination(self):
        injuries = [_make_injury_mock(id=i, name=f"Injury{i}") for i in range(25)]
        with patch("src.bot.ui.vet_clinic.list_all_injuries", new_callable=AsyncMock, return_value=injuries):
            source = InjuryListPageSource()
            await source.load()
            assert source.page_count() == ceil(25 / 10)

    async def test_render_shows_injury_names(self):
        injuries = [_make_injury_mock(id=1, name="Fracture"), _make_injury_mock(id=2, name="Sprain")]
        with patch("src.bot.ui.vet_clinic.list_all_injuries", new_callable=AsyncMock, return_value=injuries):
            source = InjuryListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Fracture" in embed.description
            assert "Sprain" in embed.description

    async def test_render_attaches_dropdown(self):
        injuries = [_make_injury_mock(id=1, name="Bruise")]
        with patch("src.bot.ui.vet_clinic.list_all_injuries", new_callable=AsyncMock, return_value=injuries):
            source = InjuryListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            await source.render(view, 0)
            assert view.add_item.called


# ---------------------------------------------------------------------------
# DiseaseListPageSource
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestDiseaseListPageSource:
    async def test_empty_diseases(self):
        with patch("src.bot.ui.vet_clinic.list_all_diseases", new_callable=AsyncMock, return_value=[]):
            source = DiseaseListPageSource()
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No diseases found" in embed.description

    async def test_disease_pagination(self):
        diseases = [MagicMock() for _ in range(12)]
        for i, d in enumerate(diseases):
            d.name = f"Disease{i}"
        with patch("src.bot.ui.vet_clinic.list_all_diseases", new_callable=AsyncMock, return_value=diseases):
            source = DiseaseListPageSource()
            await source.load()
            assert source.page_count() == ceil(12 / 10)

    async def test_render_shows_disease_names(self):
        disease = MagicMock()
        disease.name = "Kennel Cough"
        with patch("src.bot.ui.vet_clinic.list_all_diseases", new_callable=AsyncMock, return_value=[disease]):
            source = DiseaseListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Kennel Cough" in embed.description

    async def test_render_attaches_dropdown(self):
        disease = MagicMock()
        disease.name = "Parvovirus"
        with patch("src.bot.ui.vet_clinic.list_all_diseases", new_callable=AsyncMock, return_value=[disease]):
            source = DiseaseListPageSource()
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            await source.render(view, 0)
            assert view.add_item.called


# ---------------------------------------------------------------------------
# _PatientRoomView — disease diagnosis buttons
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestPatientRoomViewDiseaseDiagnosis:
    async def test_has_diagnose_diseases_button(self):
        pooch = _make_pooch_mock()
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any("Diagnose Diseases" in (b.label or "") for b in buttons)

    async def test_on_diagnose_diseases_revealed(self):
        pooch = _make_pooch_mock()
        pooch.diseases = []
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)

        interaction = MagicMock()
        with (
            patch(
                "src.bot.ui.vet_clinic.diagnose_diseases",
                new_callable=AsyncMock,
                return_value=(True, None, ["Kennel Cough"]),
            ),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_diagnose_diseases(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "Kennel Cough" in content

    async def test_on_diagnose_diseases_none_found(self):
        pooch = _make_pooch_mock()
        pooch.diseases = []
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)

        interaction = MagicMock()
        with (
            patch("src.bot.ui.vet_clinic.diagnose_diseases", new_callable=AsyncMock, return_value=(True, None, [])),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_diagnose_diseases(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "No hidden diseases" in content

    async def test_on_diagnose_diseases_failure(self):
        pooch = _make_pooch_mock()
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)

        interaction = MagicMock()
        with (
            patch(
                "src.bot.ui.vet_clinic.diagnose_diseases",
                new_callable=AsyncMock,
                return_value=(False, "Not enough money", []),
            ),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_diagnose_diseases(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "Diagnosis failed" in content or "Not enough money" in content

    async def test_on_treat_disease_no_diseases(self):
        pooch = _make_pooch_mock()
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)

        interaction = MagicMock()
        with (
            patch("src.bot.ui.vet_clinic.get_pooch_disease_instances", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_treat_disease(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "no diseases to treat" in content.lower()

    async def test_on_treat_disease_with_instances(self):
        pooch = _make_pooch_mock()
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)

        pd = MagicMock()
        pd.id = 1
        pd.treated = False
        pd.disease = MagicMock()
        pd.disease.name = "Kennel Cough"
        pd.disease.treatable = True
        pd.disease.curable = True

        interaction = MagicMock()
        with (
            patch("src.bot.ui.vet_clinic.get_pooch_disease_instances", new_callable=AsyncMock, return_value=[pd]),
            patch("src.bot.ui.vet_clinic.get_disease_treatment_cost", return_value=15),
            patch("src.bot.ui.vet_clinic.get_public_disease_label", return_value="Kennel Cough"),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_treat_disease(interaction)

        mock_r.reply.assert_called_once()
        kwargs = mock_r.reply.call_args[1]
        assert "view" in kwargs
        assert isinstance(kwargs["view"], _TreatDiseaseSelectView)

    async def test_build_embed_shows_disease_count(self):
        pd1 = MagicMock()
        pd1.visible = True
        pd2 = MagicMock()
        pd2.visible = True
        pooch = _make_pooch_mock(diseases_list=[pd1, pd2])
        with patch("src.bot.ui.vet_clinic.get_diagnose_injuries_cost", return_value=10):
            with patch("src.bot.ui.vet_clinic.get_diagnose_mutations_cost", return_value=10):
                with patch("src.bot.ui.vet_clinic.get_diagnose_diseases_cost", return_value=10):
                    view = _PatientRoomView(owner_discord_id=100, pooch=pooch)
        embed = await view.build_embed()
        assert "**Diseases:** 2" in embed.description


# ---------------------------------------------------------------------------
# _TreatDiseaseSelectView
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestTreatDiseaseSelectView:
    def _make_pd(self, id=1, name="Kennel Cough", treatable=True, curable=True, treated=False):
        pd = MagicMock()
        pd.id = id
        pd.treated = treated
        pd.disease = MagicMock()
        pd.disease.name = name
        pd.disease.treatable = treatable
        pd.disease.curable = curable
        return pd

    def _make_view(self, disease_instances=None):
        pooch = _make_pooch_mock()
        instances = disease_instances or [self._make_pd()]
        with (
            patch("src.bot.ui.vet_clinic.get_disease_treatment_cost", return_value=15),
            patch("src.bot.ui.vet_clinic.get_public_disease_label", return_value="Kennel Cough"),
        ):
            return _TreatDiseaseSelectView(
                owner_discord_id=100,
                pooch=pooch,
                disease_instances=instances,
            )

    async def test_creates_view_with_options(self):
        view = self._make_view()
        assert isinstance(view, discord.ui.View)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1

    async def test_treat_button_initially_disabled(self):
        view = self._make_view()
        assert view._treat_button.disabled is True

    async def test_build_embed_lists_diseases(self):
        view = self._make_view()
        with (
            patch("src.bot.ui.vet_clinic.get_disease_treatment_cost", return_value=15),
            patch("src.bot.ui.vet_clinic.get_public_disease_label", return_value="Kennel Cough"),
        ):
            embed = await view.build_embed()
        assert "Kennel Cough" in embed.description

    async def test_on_disease_select_enables_treat_button(self):
        view = self._make_view()
        pd = view._disease_instances[0]

        interaction = MagicMock()
        interaction.data = {"values": [str(pd.id)]}
        with patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            with patch.object(
                type(view._select),
                "values",
                new_callable=lambda: property(lambda self: [str(pd.id)]),
            ):
                await view._on_disease_select(interaction)

        assert view._treat_button.disabled is False

    async def test_on_treat_calls_treat_disease(self):
        view = self._make_view()
        pd = view._disease_instances[0]
        view._selected_pd = pd

        interaction = MagicMock()
        with (
            patch(
                "src.bot.ui.vet_clinic.treat_disease", new_callable=AsyncMock, return_value=(True, "Treated!", 15)
            ) as mock_treat,
            patch("src.bot.ui.vet_clinic.get_pooch_disease_instances", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.vet_clinic.get_disease_treatment_cost", return_value=15),
            patch("src.bot.ui.vet_clinic.get_public_disease_label", return_value="Kennel Cough"),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_treat(interaction)

        mock_treat.assert_called_once_with(100, pd.id)

    async def test_on_treat_success_refreshes_view(self):
        view = self._make_view()
        pd = view._disease_instances[0]
        view._selected_pd = pd

        interaction = MagicMock()
        with (
            patch("src.bot.ui.vet_clinic.treat_disease", new_callable=AsyncMock, return_value=(True, "Treated!", 15)),
            patch(
                "src.bot.ui.vet_clinic.get_pooch_disease_instances", new_callable=AsyncMock, return_value=[]
            ) as mock_refresh,
            patch("src.bot.ui.vet_clinic.get_disease_treatment_cost", return_value=15),
            patch("src.bot.ui.vet_clinic.get_public_disease_label", return_value="Kennel Cough"),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_treat(interaction)

        mock_refresh.assert_called_once()
        mock_r.edit.assert_called()

    async def test_on_treat_failure_replies_ephemeral_error(self):
        view = self._make_view()
        pd = view._disease_instances[0]
        view._selected_pd = pd

        interaction = MagicMock()
        with (
            patch(
                "src.bot.ui.vet_clinic.treat_disease",
                new_callable=AsyncMock,
                return_value=(False, "Already treated today", 0),
            ),
            patch("src.bot.ui.vet_clinic.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_treat(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "Treatment failed" in content or "Already treated" in content
