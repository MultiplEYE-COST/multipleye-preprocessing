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

:::{dropdown} Who is this pipeline intended for?
:open:

There are two primary use cases for this pipeline:
* Researchers who are part of the MultiplEYE network and have collected eye-tracking and / or psychometric test data. You can use this pipeline to preprocess the data.
* Students or researchers who are interested in learning about eye-tracking data preprocessing.
You can use this pipeline to explore the preprocessing steps and understand how raw eye-tracking data is transformed
into a standardized format for analysis. In this case, we refer to the tutorial notebook described in {ref}`getting_started`.
:::

:::{dropdown} Can I use the pipeline with eye-tracking data other than MultiplEYE?

At the moment, the pipeline is designed to work with data collected in the MultiplEYE project.
However, if your data is in a compatible format and you are willing to adapt the code,
it may be possible to use the pipeline for other eye-tracking datasets. In any case, please contact the maintainers if you
are interested to adapt the pipeline to other datasets.
:::

:::{dropdown} How long does preprocessing typically take?

Given that the .edf files need to be converted to .asc files first, the preprocessing time can vary depending on the
number of sessions and the size of the data. However, for the size of the MultiplEYE datasets, which include about 100 sessions,
it can take a few hours.
:::

(faq_equipment)=

## Eye-Tracking Equipment

:::{dropdown} What eye-trackers are supported?

Currently, we support EyeLink eye-trackers with head-stabilized tracking.
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
