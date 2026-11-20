(faq)=

# Frequently Asked Questions

If you have a question that is not answered there, please reach out to the maintainers.

---

```{eval-rst}
.. raw:: html

   <div class="faq-search-container">
       <input type="text" id="faq-search" placeholder="Search FAQs...">
   </div>
```

(faq_general)=

## General

:::{dropdown} Who is the pEYEpline intended for?
:open:

There are two primary use cases for the pEYEpline:
* Researchers who are part of the MultiplEYE network and have collected eye-tracking and / or psychometric test data. You can use the pEYEpline to preprocess the data.
* Students or researchers who are interested in learning about eye-tracking data preprocessing.
You can use the pEYEpline to explore the preprocessing steps and understand how raw eye-tracking data is transformed
into a standardized format for analysis. In this case, we refer to the tutorial notebook described in {ref}`getting_started`.
:::

:::{dropdown} Can I use the pEYEpline with eye-tracking data other than MultiplEYE?

At the moment, the pEYEpline is designed to work with data collected in the MultiplEYE project.
However, if your data is in a compatible format and you are willing to adapt the code,
it may be possible to use the pEYEpline for other eye-tracking datasets. In any case, please contact the maintainers if you
are interested to adapt the pEYEpline to other datasets.
:::

:::{dropdown} How long does preprocessing typically take?

Given that the .edf files need to be converted to .asc files first, the preprocessing time can vary depending on the
number of sessions and the size of the data. However, for the size of the MultiplEYE datasets, which include about 100 sessions,
it can take a few hours.
:::

:::{dropdown} What happens when the stimulus folder is updated?
:open:

The pEYEpline remembers which stimulus files it copied last time.
If the source folder has changed since then (for example, after a team uploads
a corrected version), the pEYEpline notices the difference and copies the updated
folder automatically. No manual action needed.
:::

:::{dropdown} Do I need psychometric test data to run the pEYEpline?

No. Psychometric tests are a separate stage. If the collection has no
`psychometric-tests-sessions/` folder or no recognizable test data, the stage is skipped and the
pipeline processes the eye-tracking data normally.

If no psychometric tests were collected, set `RUN_PSYCHOMETRIC_TESTS: false` in the settings file
to stop the related warnings. If tests were collected but skipped, see the psychometric test
sections of the troubleshooting page.
:::

:::{dropdown} Why does the pEYEpline continue after a warning?

Warnings describe data that were skipped, a fallback that was used, or a quality problem that does
not stop the pipeline. For example, a session without an EDF file still contributes comprehension
answers, and a collection without psychometric test data still produces eye-tracking outputs.

Errors stop the stage or the run because continuing would produce wrong results. Read the message
to decide whether a warning is expected. If it is not, fix the input and rerun the affected
session with `recalculate: true`. The troubleshooting page lists the common warnings and errors.
:::

(faq_equipment)=

## Eye-Tracking Equipment

:::{dropdown} What eye-trackers are supported?

The pipeline currently supports `EyeLink 1000`, `EyeLink 1000 Plus`, `EyeLink II` and
`EyeLink Portable Duo` with head-stabilized tracking. Common lab-configuration spellings are
normalized; for example, `EyeLink Duo` and `EyeLink Portable Duo 2000Hz Remote` are stored as
`EyeLink Portable Duo`. An unsupported name stops preprocessing and lists close matches.
:::


---

```{eval-rst}
.. raw:: html

   <div id="faq-no-results" class="faq-no-results" style="display: none;">
       No results found. Try a different search term.
   </div>
```

---

```{eval-rst}
.. raw:: html

   <div id="faq-fallback" class="faq-fallback">
       <em>If none of this works, maybe look on the <a href="../troubleshooting">Troubleshooting</a> page for answers. Finally, you can reach out to the maintainers.</em>
   </div>
```
